"""Shared DOM utilities — single source of truth for radio group discovery.

All DOM analysis is done in a single page.evaluate() call to avoid
per-element Python↔JS round-trips (critical for pages with many radios).
"""

from playwright.sync_api import Page, Locator


def extract_all_questions(page: Page) -> list[dict]:
    """Extract all question data from the page in a single JS call.

    Returns a list of dicts, each representing one question group:
        {title, options: [{label, has_text_input}, ...], input_type: "radio"|"checkbox"|"select"|"text"}
    """
    return page.evaluate(
        """() => {
            const radios = document.querySelectorAll('input[type="radio"]');
            if (!radios.length) return [];

            const radiosArr = Array.from(radios);

            // ================================================================
            // Step 1: Group radios into question groups
            // ================================================================
            let groups = _groupRadios(radiosArr);

            // ================================================================
            // Step 2: Extract title + options for each group
            // ================================================================
            return groups.map(g => {
                const firstRadio = g.radios[0];
                const title = _extractTitle(firstRadio, g.radios);
                let options = g.radios.map((r, idx) => ({
                    label: _extractLabel(r, idx),
                    has_text_input: _hasTextInput(r),
                }));

                // Normalize: ensure index 0 = worst, index N-1 = best.
                let wasReversed = false;
                if (options.length >= 2) {
                    const first = options[0].label || '';
                    const last = options[options.length - 1].label || '';
                    const firstBest = first.includes('非常同意') || first.includes('Strongly Agree')
                        || first.includes('强烈推荐') || first.includes('Strongly Recommend')
                        || first.includes('一定会') || first.includes('Definitely');
                    const lastWorst = last.includes('非常不同意') || last.includes('Strongly Disagree')
                        || last.includes('强烈不推荐') || last.includes('Strongly Do Not Recommend')
                        || last.includes('一定不会') || last.includes('Definitely Not');
                    if (firstBest && lastWorst) {
                        options.reverse();
                        wasReversed = true;
                    }
                }

                return {title: title, options: options, _was_reversed: wasReversed};
            });

            // --- Helper functions ---

            function _groupRadios(radiosArr) {
                // Strategy A: group by HTML name attribute
                const nameGroups = {};
                let hasNames = false;
                for (const r of radiosArr) {
                    const n = r.getAttribute('name');
                    if (n) { hasNames = true; (nameGroups[n] ||= []).push(r); }
                }
                if (hasNames) {
                    const groups = Object.entries(nameGroups).map(([k, rs]) => ({key: k, radios: rs}));
                    if (Math.max(...groups.map(g => g.radios.length)) <= 10) return groups;
                }

                // Strategy B: group by structural container
                const containerGroups = _groupByContainer(radiosArr);
                if (Math.max(...containerGroups.map(g => g.radios.length)) <= 10) return containerGroups;

                // Strategy C: group by value-sequence pattern
                // When all else fails, detect question boundaries by
                // watching for value resets (e.g., 5→1 or 1→5 transitions)
                return _groupByValuePattern(radiosArr);
            }

            function _groupByContainer(radiosArr) {
                const findContainer = (r) => {
                    let c = r.parentElement;
                    for (let i = 0; i < 6; i++) {
                        if (!c || c === document.body) break;
                        const tag = c.tagName;
                        const cls = (c.className || '').toString();
                        if (tag === 'TR' || tag === 'LI') break;
                        if (tag === 'TD' || tag === 'TH') break;
                        if (tag === 'DIV' && /(?:question|item|group|row|el-form|form-item|field)/i.test(cls)) break;
                        c = c.parentElement;
                    }
                    return (c && c !== document.body) ? c : r.parentElement;
                };

                const getKey = (c) => {
                    if (!c || c === document.body) return 'root';
                    const cls = (c.className && typeof c.className === 'string')
                        ? c.className.split(/\\s+/).filter(s => s && s !== 'active').slice(0,2).join('.')
                        : '';
                    const idx = c.parentElement
                        ? [...c.parentElement.children].filter(ch => ch.tagName === c.tagName).indexOf(c)
                        : 0;
                    return c.tagName + '|' + cls + '|' + idx;
                };

                const cids = radiosArr.map(r => getKey(findContainer(r)));
                const seen = new Map();
                const indices = cids.map(k => {
                    if (!seen.has(k)) seen.set(k, seen.size);
                    return seen.get(k);
                });

                const groups = {};
                for (let i = 0; i < radiosArr.length; i++) {
                    (groups[indices[i]] ||= []).push(radiosArr[i]);
                }
                return Object.entries(groups).map(([k, rs]) => ({key: 'c.' + k, radios: rs}));
            }

            function _groupByValuePattern(radiosArr) {
                // Detect question boundaries by trend-reversal of radio values.
                // Within a group, values either monotonically descend (5→4→3→2→1)
                // or ascend (1→2→3→4→5). A boundary occurs when the trend reverses.
                const groups = [];
                let current = [radiosArr[0]];

                // Determine the dominant trend from the first pair
                const firstVal = parseInt(radiosArr[0].getAttribute('value')) || 0;
                const secondVal = radiosArr.length >= 2 ? (parseInt(radiosArr[1].getAttribute('value')) || 0) : firstVal;
                const trendDescending = firstVal > secondVal;
                // descending: boundary when prev < curr (value goes UP, restarting sequence)
                // ascending:  boundary when prev > curr (value goes DOWN, restarting sequence)

                for (let i = 1; i < radiosArr.length; i++) {
                    const prev = radiosArr[i - 1];
                    const curr = radiosArr[i];

                    const prevName = prev.getAttribute('name') || '';
                    const currName = curr.getAttribute('name') || '';
                    const nameChanged = prevName && currName && prevName !== currName;

                    const prevVal = parseInt(prev.getAttribute('value')) || 0;
                    const currVal = parseInt(curr.getAttribute('value')) || 0;

                    // Boundary: trend reversal (opposite of within-group direction)
                    const trendReversed = trendDescending ? (prevVal < currVal) : (prevVal > currVal);

                    if (nameChanged || trendReversed) {
                        groups.push({key: 'v.' + groups.length, radios: current});
                        current = [curr];
                    } else {
                        current.push(curr);
                    }
                }
                if (current.length > 0) {
                    groups.push({key: 'v.' + groups.length, radios: current});
                }
                return groups;
            }

            function _extractTitle(firstRadio, groupRadios) {
                // Walk up from the radio, checking preceding siblings at each level.
                let el = firstRadio;
                let formItemEl = null;
                for (let i = 0; i < 10; i++) {
                    el = el.parentElement;
                    if (!el || el === document.body) break;

                    const cls = (el.className || '').toString();

                    // Skip radio-option-level wrappers
                    if (/\\b(?:el-radio|ant-radio)\\b/.test(cls) && !/\\b(?:el-radio-group|ant-radio-group)\\b/.test(cls)) continue;
                    if (el.tagName === 'LABEL' && /\\bradio\\b/.test(cls)) continue;

                    // Check preceding siblings at this level
                    let prev = el.previousElementSibling;
                    while (prev) {
                        // Stop at another question (has radios)
                        if (prev.querySelector('input[type="radio"]')) break;
                        const t = prev.textContent.trim();
                        if (t.length > 3 && t.length < 200) return t.slice(0, 200);
                        prev = prev.previousElementSibling;
                    }

                    // Remember form-item for later label lookup
                    if (/\\b(?:ant-form-item|el-form-item)\\b/.test(cls) && !/\\b(?:ant-form-item-control|el-form-item__content)\\b/.test(cls)) {
                        formItemEl = el;
                    }

                    // Stop when we reach the form-item container (Ant Design or Element UI)
                    if (/\\b(?:ant-form-item|el-form-item)\\b/.test(cls) && !/\\b(?:ant-form-item-control|el-form-item__content)\\b/.test(cls)) break;
                }

                // Strategy B: look for .ant-form-item-label / .el-form-item__label
                // within the form-item (preceding sibling of control-wrapper)
                if (formItemEl) {
                    const labelDiv = formItemEl.querySelector('.ant-form-item-label, .el-form-item__label');
                    if (labelDiv) {
                        const t = labelDiv.textContent.trim();
                        if (t.length > 1 && t.length < 200) return t.slice(0, 200);
                    }
                    // Also check direct children that are label-like
                    for (const child of formItemEl.children) {
                        if (child.querySelector('input[type="radio"]')) continue;
                        const childCls = (child.className || '').toString();
                        if (/\\b(?:ant-form-item-control|el-form-item__content)\\b/.test(childCls)) continue;
                        const t = child.textContent.trim();
                        if (t.length > 1 && t.length < 200) return t.slice(0, 200);
                    }
                }

                // Strategy C: check parent of form-item (content container) AND
                // grandparent (subject container) for siblings with title-like classes
                for (let level = 0; level < 2; level++) {
                    const container = level === 0
                        ? (formItemEl ? formItemEl.parentElement : null)        // content container
                        : (formItemEl && formItemEl.parentElement ? formItemEl.parentElement.parentElement : null);  // subject container

                    if (!container) continue;

                    for (const child of container.children) {
                        if (child === (level === 0 ? formItemEl : formItemEl.parentElement)) continue;
                        if (child.querySelector('input[type="radio"]')) continue;
                        const childCls = (child.className || '').toString();
                        const tag = child.tagName;
                        // Heading elements or title-like classes (including CSS module patterns)
                        if (/^H[1-6]$/.test(tag) || /(?:^|[\\s_-])(title|label|header|question|prompt)(?:[\\s_-]|$)/i.test(childCls)) {
                            const t = child.textContent.trim();
                            if (t.length > 1 && t.length < 500) return t.slice(0, 200);
                        }
                    }
                    // Fallback: any sibling without a radio
                    for (const child of container.children) {
                        if (child === (level === 0 ? formItemEl : formItemEl.parentElement)) continue;
                        if (child.querySelector('input[type="radio"]')) continue;
                        const t = child.textContent.trim();
                        if (t.length > 3 && t.length < 500) return t.slice(0, 200);
                    }
                }

                // Strategy D: check for fieldset > legend
                {
                    let walk = firstRadio;
                    for (let i = 0; i < 8; i++) {
                        walk = walk.parentElement;
                        if (!walk || walk === document.body) break;
                        if (walk.tagName === 'FIELDSET') {
                            const legend = walk.querySelector(':scope > legend');
                            if (legend) {
                                const t = legend.textContent.trim();
                                if (t.length > 1 && t.length < 200) return t.slice(0, 200);
                            }
                        }
                    }
                }

                // Strategy E: check aria-labelledby on ancestors
                {
                    let walk = firstRadio;
                    for (let i = 0; i < 6; i++) {
                        walk = walk.parentElement;
                        if (!walk || walk === document.body) break;
                        const labelledBy = walk.getAttribute('aria-labelledby');
                        if (labelledBy) {
                            const labelEl = document.getElementById(labelledBy);
                            if (labelEl) {
                                const t = labelEl.textContent.trim();
                                if (t.length > 1 && t.length < 200) return t.slice(0, 200);
                            }
                        }
                    }
                }

                return '未知题目';
            }

            function _containsAnyRadio(el, groupRadios) {
                for (const r of groupRadios) {
                    if (el.contains(r)) return true;
                }
                return false;
            }

            function _extractLabel(r, idx) {
                let label = '';

                // 1. aria-label
                label = (r.getAttribute('aria-label') || '').trim();

                // 2. <label for="radioId">
                if (!label) {
                    const id = r.getAttribute('id');
                    if (id) {
                        try {
                            const lbl = document.querySelector('label[for="' + CSS.escape(id) + '"]');
                            if (lbl) label = lbl.textContent.trim();
                        } catch(e) {}
                    }
                }

                // 3. Parent <label> wrapper
                if (!label) {
                    const p = r.parentElement;
                    if (p && p.tagName === 'LABEL') label = p.textContent.trim();
                }

                // 4. Next sibling
                if (!label) {
                    let sib = r.nextElementSibling;
                    if (sib && (sib.tagName === 'LABEL' || sib.tagName === 'SPAN')) {
                        label = sib.textContent.trim();
                    }
                }

                // 5. Previous sibling
                if (!label) {
                    let sib = r.previousElementSibling;
                    if (sib && (sib.tagName === 'LABEL' || sib.tagName === 'SPAN')) {
                        label = sib.textContent.trim();
                    }
                }

                // 6. Sibling text in parent
                if (!label || label.length > 100) {
                    const p = r.parentElement;
                    if (p) {
                        for (const child of p.children) {
                            if (child === r) continue;
                            const t = child.textContent.trim();
                            if (t && t.length >= 1 && t.length < 50) { label = t; break; }
                        }
                    }
                }

                // 7. Grandparent sibling text (Element UI: el-radio__label next to el-radio__input)
                if (!label || label.length > 100) {
                    const gp = r.parentElement ? r.parentElement.parentElement : null;
                    if (gp) {
                        for (const child of gp.children) {
                            if (child.contains(r)) continue;
                            const t = child.textContent.trim();
                            if (t && t.length >= 1 && t.length < 50) { label = t; break; }
                        }
                    }
                }

                // 8. Generic walk-up: look for text siblings at any ancestor level
                if (!label || label.length > 100) {
                    let walk = r.parentElement;
                    for (let j = 0; j < 5; j++) {
                        if (!walk || walk === document.body) break;
                        for (const child of walk.children) {
                            if (child.contains(r)) continue;
                            const t = child.textContent.trim();
                            if (t && t.length >= 1 && t.length < 50 && !/^[0-9\\s.]+$/.test(t)) {
                                label = t;
                                break;
                            }
                        }
                        if (label && label.length < 50) break;
                        walk = walk.parentElement;
                    }
                }

                // 9. Fallback: value attribute or index
                if (!label || label.length > 100) {
                    label = r.getAttribute('value') || ('选项' + (idx + 1));
                }

                return label;
            }

            function _hasTextInput(r) {
                // Check ancestors for text inputs (including hidden ones that
                // appear conditionally when this option is selected).
                let walk = r.parentElement;
                for (let j = 0; j < 5; j++) {
                    if (!walk) break;
                    const inputs = walk.querySelectorAll('input[type="text"], textarea, [contenteditable="true"]');
                    if (inputs.length > 0) return true;
                    walk = walk.parentElement;
                }
                // Heuristic: does this option's label suggest a text response?
                // Check aria-label, parent text, and nearby elements
                let labelText = (r.getAttribute('aria-label') || '').trim();
                if (!labelText) {
                    // Try parent LABEL or wrapper
                    let p = r.parentElement;
                    for (let j = 0; j < 3 && p; j++) {
                        labelText = (p.textContent || '').trim();
                        if (labelText.length > 0 && labelText.length < 100) break;
                        p = p.parentElement;
                    }
                }
                if (/\\(?:其他|其它|请注明|请说明|请填写|请补充|请具体|other|specify|explain|describe\\)/i.test(labelText)) return true;
                return false;
            }
        }"""
    )


def get_radio_groups(page: Page) -> dict[str, list[Locator]]:
    """Get radio button groups for form-filling operations.

    Returns dict in DOM order: {group_key: [radio_locators]}.
    """
    radio_inputs = page.locator('input[type="radio"]').all()
    if not radio_inputs:
        return {}
    return _group_locators(radio_inputs)


def _group_locators(radio_inputs: list[Locator]) -> dict[str, list[Locator]]:
    """Group radio locators by name attribute, structural position, or value pattern.

    Must match the grouping logic in extract_all_questions' _groupRadios().
    Also normalizes radio order within each group to ascending values.
    """
    if not radio_inputs:
        return {}

    # Try name first
    groups: dict[str, list[Locator]] = {}
    has_names = False
    for radio in radio_inputs:
        try:
            name = radio.get_attribute("name")
        except Exception:
            continue
        if name:
            has_names = True
            if name not in groups:
                groups[name] = []
            groups[name].append(radio)

    if has_names:
        max_size = max((len(v) for v in groups.values()), default=0)
        if max_size <= 10:
            return groups  # Keep raw page order; normalization handled in fill_form

    # Try container-based grouping
    groups = _group_by_container_eval(radio_inputs)
    max_size = max((len(v) for v in groups.values()), default=0)
    if max_size <= 10:
        return groups  # Keep raw page order; normalization handled in fill_form

    # Value-pattern fallback (may normalize internally, but fill_form will re-check)
    return _group_by_value_pattern(radio_inputs)


def _group_by_container_eval(radio_inputs: list[Locator]) -> dict[str, list[Locator]]:
    """Group radios by structural container using a single JS evaluation.

    Uses nth-child indexing to create stable IDs for each container,
    then matches them back to Python locators.
    """
    if not radio_inputs:
        return {}

    page = radio_inputs[0].page

    # JS returns container index for each radio in DOM order
    container_indices = page.evaluate(
        """() => {
            const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
            if (!radios.length) return [];

            const getContainerKey = (c) => {
                if (!c || c === document.body) return 'root';
                return c.tagName + '|' +
                    ((c.className && typeof c.className === 'string')
                        ? c.className.split(/\\s+/).filter(s => s && s !== 'active').slice(0,2).join('.')
                        : '') + '|' +
                    (c.parentElement ? [...c.parentElement.children]
                        .filter(ch => ch.tagName === c.tagName).indexOf(c) : 0);
            };

            const findContainer = (r) => {
                let c = r.parentElement;
                for (let i = 0; i < 6; i++) {
                    if (!c || c === document.body) break;
                    const tag = c.tagName;
                    const cls = (c.className || '').toString();
                    if (tag === 'TR' || tag === 'LI') break;
                    if (tag === 'TD' || tag === 'TH') break;
                    if (tag === 'DIV' && /(?:question|item|group|row|el-form|form-item|field)/i.test(cls)) break;
                    c = c.parentElement;
                }
                if (!c || c === document.body) c = r.parentElement;
                return c;
            };

            // First pass: find containers
            const keys = radios.map(r => getContainerKey(findContainer(r)));
            let groups = {};
            keys.forEach(k => { groups[k] = (groups[k] || 0) + 1; });
            const maxSize = Math.max(...Object.values(groups));

            // If any group too large, fallback to parent-level grouping
            if (maxSize > 10) {
                const keys2 = radios.map(r => getContainerKey(r.parentElement));
                groups = {};
                keys2.forEach(k => { groups[k] = (groups[k] || 0) + 1; });
                const maxSize2 = Math.max(...Object.values(groups));
                if (maxSize2 > 10) {
                    // Grandparent fallback
                    const keys3 = radios.map(r => getContainerKey(
                        r.parentElement ? r.parentElement.parentElement : r.parentElement));
                    const seen = new Map();
                    return keys3.map(k => {
                        if (!seen.has(k)) seen.set(k, seen.size);
                        return seen.get(k);
                    });
                }
                const seen = new Map();
                return keys2.map(k => {
                    if (!seen.has(k)) seen.set(k, seen.size);
                    return seen.get(k);
                });
            }

            const seen = new Map();
            return keys.map(k => {
                if (!seen.has(k)) seen.set(k, seen.size);
                return seen.get(k);
            });
        }"""
    )

    if not container_indices or len(container_indices) != len(radio_inputs):
        # Fallback: every radio is its own group
        return {f"r.{i}": [r] for i, r in enumerate(radio_inputs)}

    groups: dict[str, list[Locator]] = {}
    for idx, radio in zip(container_indices, radio_inputs):
        key = f"g.{idx}"
        if key not in groups:
            groups[key] = []
        groups[key].append(radio)

    return groups


def _group_by_value_pattern(radio_inputs: list[Locator]) -> dict[str, list[Locator]]:
    """Group radios by detecting value-sequence resets (e.g., 5→1 pattern).

    Used as last-resort fallback when name-based and container-based grouping fail.
    Also normalizes radio order within each group to ascending values.
    """
    if not radio_inputs:
        return {}

    page = radio_inputs[0].page

    # Get value and name attributes for all radios in DOM order (single JS call)
    radio_attrs = page.evaluate(
        """() => {
            return Array.from(document.querySelectorAll('input[type="radio"]'))
                .map(r => ({
                    value: parseInt(r.getAttribute('value')) || 0,
                    name: r.getAttribute('name') || '',
                }));
        }"""
    )

    if not radio_attrs or len(radio_attrs) != len(radio_inputs):
        return {f"r.{i}": [r] for i, r in enumerate(radio_inputs)}

    # Determine trend from first pair
    first_val = radio_attrs[0]['value']
    second_val = radio_attrs[1]['value'] if len(radio_attrs) >= 2 else first_val
    trend_descending = first_val > second_val

    # Detect group boundaries by trend reversal
    group_boundaries = [0]
    for i in range(1, len(radio_attrs)):
        prev = radio_attrs[i - 1]
        curr = radio_attrs[i]

        name_changed = prev['name'] and curr['name'] and prev['name'] != curr['name']
        trend_reversed = (prev['value'] < curr['value']) if trend_descending else (prev['value'] > curr['value'])

        if name_changed or trend_reversed:
            group_boundaries.append(i)

    # Build groups, normalizing order within each group to ascending values
    groups: dict[str, list[Locator]] = {}
    for g_idx, start in enumerate(group_boundaries):
        end = group_boundaries[g_idx + 1] if g_idx + 1 < len(group_boundaries) else len(radio_inputs)
        key = f"v.{g_idx}"
        groups[key] = radio_inputs[start:end]

    return groups


def find_associated_text_input(page: Page, radio_element: Locator) -> Locator | None:
    """Find and return a text input associated with a radio option.

    Handles both static and conditionally-rendered inputs (e.g., Ant Design
    forms where a textarea appears after selecting a specific radio option).
    """
    try:
        # Strategy 1: search within form-item container
        for xpath in [
            "xpath=ancestor::*[contains(@class, 'ant-form-item')][1]",
            "xpath=ancestor::*[contains(@class, 'el-form-item')][1]",
            "xpath=ancestor::tr[1]",
            "xpath=../../../..",
        ]:
            try:
                ancestor = radio_element.locator(xpath)
                if ancestor.count() == 0:
                    continue
                for selector in ['input[type="text"]', "textarea", '[contenteditable="true"]']:
                    inputs = ancestor.locator(selector).all()
                    for inp in inputs:
                        if inp.is_visible():
                            return inp
            except Exception:
                continue

        # Strategy 2: vertical proximity search (wider range for conditional inputs)
        rb = radio_element.bounding_box()
        if rb:
            all_inputs = page.locator('input[type="text"], textarea').all()
            best = None
            best_dist = float("inf")
            for inp in all_inputs:
                try:
                    bb = inp.bounding_box()
                    if bb and inp.is_visible():
                        dist = abs(bb["y"] - rb["y"])
                        if dist < best_dist:
                            best_dist = dist
                            best = inp
                except Exception:
                    continue
            if best and best_dist < 250:
                return best
    except Exception:
        pass
    return None


def scan_all_form_elements(page: Page) -> dict:
    """Scan page for ALL form item containers and their input types.

    Returns counts and details for debugging missing questions.
    """
    return page.evaluate(
        """() => {
            const result = {
                radios: 0,
                radio_groups: 0,
                checkboxes: 0,
                selects: 0,
                textareas: 0,
                text_inputs: 0,
                form_items: 0,
                details: [],
                item_summary: [],
            };

            // Count basic elements
            result.radios = document.querySelectorAll('input[type="radio"]').length;
            result.checkboxes = document.querySelectorAll('input[type="checkbox"]').length;
            result.selects = document.querySelectorAll('select').length;
            result.textareas = document.querySelectorAll('textarea').length;
            result.text_inputs = document.querySelectorAll('input[type="text"]').length;

            // Get unique radio group names
            const radioNames = new Set();
            document.querySelectorAll('input[type="radio"]').forEach(r => {
                const n = r.getAttribute('name');
                if (n) radioNames.add(n);
            });
            result.radio_groups = radioNames.size || result.radios;

            // ================================================================
            // Scan by ant-form-item / el-form-item containers
            // ================================================================
            const formItems = document.querySelectorAll('.ant-form-item, .el-form-item');
            result.form_items = formItems.length;
            formItems.forEach((item, idx) => {
                const hasRadio = item.querySelector('input[type="radio"]');
                const hasCheckbox = item.querySelector('input[type="checkbox"]');
                const hasSelect = item.querySelector('select');
                const hasTextarea = item.querySelector('textarea');
                const hasTextInput = item.querySelector('input[type="text"]');

                // Extract label
                let label = '';
                const labelDiv = item.querySelector('.ant-form-item-label, .el-form-item__label');
                if (labelDiv) {
                    label = labelDiv.textContent.trim().slice(0, 80);
                }
                if (!label) {
                    // Check preceding sibling
                    let prev = item.previousElementSibling;
                    while (prev) {
                        if (prev.querySelector('input, select, textarea')) break;
                        const t = prev.textContent.trim();
                        if (t.length > 2 && t.length < 150) { label = t.slice(0, 80); break; }
                        prev = prev.previousElementSibling;
                    }
                }
                if (!label) {
                    // Check first child text
                    for (const child of item.children) {
                        if (child.querySelector('input[type="radio"], input[type="checkbox"]')) continue;
                        const t = child.textContent.trim();
                        if (t.length > 2 && t.length < 150) { label = t.slice(0, 80); break; }
                    }
                }

                const types = [];
                if (hasRadio) types.push('radio');
                if (hasCheckbox) types.push('checkbox');
                if (hasSelect) types.push('select');
                if (hasTextarea) types.push('textarea');
                if (hasTextInput && !hasRadio && !hasCheckbox) types.push('text');

                result.item_summary.push({
                    idx: idx,
                    label: label || '(无标签)',
                    types: types.join('+'),
                    radioCount: hasRadio ? item.querySelectorAll('input[type="radio"]').length : 0,
                });
            });

            // Non-radio form elements not inside form-items
            document.querySelectorAll('input[type="checkbox"], select, textarea').forEach(el => {
                // Skip if already inside a form-item
                let inFormItem = false;
                let walk = el.parentElement;
                for (let i = 0; i < 6; i++) {
                    if (!walk) break;
                    if (/\\b(?:ant-form-item|el-form-item)\\b/.test(walk.className || '')) {
                        inFormItem = true;
                        break;
                    }
                    walk = walk.parentElement;
                }
                if (inFormItem) return;

                let label = '';
                walk = el;
                for (let i = 0; i < 5; i++) {
                    let prev = walk.previousElementSibling;
                    while (prev) {
                        const t = prev.textContent.trim();
                        if (t.length > 2 && t.length < 150 && !prev.querySelector('input, select, textarea')) {
                            label = t.slice(0, 100);
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }
                    if (label) break;
                    walk = walk.parentElement;
                    if (!walk || walk === document.body) break;
                }
                result.details.push({
                    tag: el.tagName,
                    type: el.getAttribute('type') || '',
                    name: el.getAttribute('name') || '',
                    id: el.getAttribute('id') || '',
                    placeholder: (el.getAttribute('placeholder') || '').slice(0, 60),
                    nearby_label: label || '(独立元素)',
                });
            });

            return result;
        }"""
    )


def extract_checkbox_questions(page: Page) -> list[dict]:
    """Extract checkbox (multi-select) questions from the page.

    Returns same format as extract_all_questions:
        {title, options: [{label, has_text_input}, ...], input_type: "checkbox"}
    """
    return page.evaluate(
        """() => {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            if (!checkboxes.length) return [];

            const checkboxArr = Array.from(checkboxes);

            // Filter out table header checkboxes (Ant Design table column toggles)
            const questionCheckboxes = checkboxArr.filter(cb => {
                let walk = cb.parentElement;
                for (let i = 0; i < 6; i++) {
                    if (!walk || walk === document.body) break;
                    const cls = (walk.className || '').toString();
                    // Skip table-related elements
                    if (/\\b(?:ant-table|table-header|column-setting)\\b/i.test(cls)) return false;
                    // Stop at form-item
                    if (/\\bant-form-item\\b/.test(cls)) return true;
                    walk = walk.parentElement;
                }
                // If not in form-item, check if it looks like a question checkbox
                // (has a nearby label that looks like a question)
                let label = '';
                let w = cb.parentElement;
                for (let i = 0; i < 4; i++) {
                    if (!w) break;
                    const t = w.textContent.trim();
                    if (t.length > 3 && t.length < 200 && !/\\b(?:设置|setting|显示|hidden|column)\\b/i.test(t)) {
                        label = t;
                        break;
                    }
                    w = w.parentElement;
                }
                return label.length > 0;
            });

            if (!questionCheckboxes.length) return [];

            // Group checkboxes by form-item container
            const groups = {};
            questionCheckboxes.forEach(cb => {
                let container = null;
                let walk = cb.parentElement;
                for (let i = 0; i < 6; i++) {
                    if (!walk || walk === document.body) break;
                    const cls = (walk.className || '').toString();
                    if (/\\bant-form-item\\b/.test(cls)) {
                        container = walk;
                        break;
                    }
                    walk = walk.parentElement;
                }
                const key = container ? 'fi.' + [...document.querySelectorAll('.ant-form-item')].indexOf(container) : 'loose';
                if (!groups[key]) groups[key] = [];
                groups[key].push(cb);
            });

            // Build question data for each group
            return Object.entries(groups).map(([key, cbs]) => {
                const firstCb = cbs[0];

                // Extract title
                let title = '未知题目';
                let el = firstCb;
                for (let i = 0; i < 8; i++) {
                    if (!el || el === document.body) break;

                    // Check preceding siblings
                    let prev = el.previousElementSibling;
                    while (prev) {
                        if (prev.querySelector('input[type="radio"], input[type="checkbox"]')) break;
                        const t = prev.textContent.trim();
                        if (t.length > 3 && t.length < 200) {
                            title = t.slice(0, 200);
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }
                    if (title !== '未知题目') break;

                    // Check for form-item-label
                    const cls = (el.className || '').toString();
                    if (/\\bant-form-item\\b/.test(cls)) {
                        const labelDiv = el.querySelector('.ant-form-item-label');
                        if (labelDiv) {
                            const t = labelDiv.textContent.trim();
                            if (t.length > 1 && t.length < 200) { title = t.slice(0, 200); break; }
                        }
                        // Check parent (content container) AND grandparent (subject container)
                        for (let level = 0; level < 2; level++) {
                            const container = level === 0 ? el.parentElement : (el.parentElement ? el.parentElement.parentElement : null);
                            if (!container) continue;
                            const skipChild = level === 0 ? el : el.parentElement;
                            for (const child of container.children) {
                                if (child === skipChild) continue;
                                if (child.querySelector('input[type="radio"], input[type="checkbox"]')) continue;
                                const childCls = (child.className || '').toString();
                                if (/\\b(?:title|label|header|question)\\b/i.test(childCls) || /^H[1-6]$/.test(child.tagName)) {
                                    const t = child.textContent.trim();
                                    if (t.length > 1 && t.length < 500) { title = t.slice(0, 200); break; }
                                }
                            }
                            if (title !== '未知题目') break;
                            for (const child of container.children) {
                                if (child === skipChild) continue;
                                if (child.querySelector('input[type="radio"], input[type="checkbox"]')) continue;
                                const t = child.textContent.trim();
                                if (t.length > 3 && t.length < 500) { title = t.slice(0, 200); break; }
                            }
                            if (title !== '未知题目') break;
                        }
                        break;
                    }

                    el = el.parentElement;
                }

                // Extract option labels
                const options = cbs.map((cb, idx) => {
                    let label = '';
                    // 1. aria-label
                    label = (cb.getAttribute('aria-label') || '').trim();

                    // 2. <label for="checkboxId">
                    if (!label) {
                        const id = cb.getAttribute('id');
                        if (id) {
                            try {
                                const lbl = document.querySelector('label[for="' + CSS.escape(id) + '"]');
                                if (lbl) label = lbl.textContent.trim();
                            } catch(e) {}
                        }
                    }

                    // 3. Ant Design: input → span.ant-checkbox → label.ant-checkbox-wrapper
                    //    The text is in a sibling <span> of span.ant-checkbox inside the label
                    if (!label) {
                        const checkboxSpan = cb.parentElement;  // span.ant-checkbox
                        if (checkboxSpan) {
                            const wrapper = checkboxSpan.parentElement;  // label.ant-checkbox-wrapper or span
                            if (wrapper) {
                                // Look for text in siblings of the checkbox span
                                for (const child of wrapper.children) {
                                    if (child === checkboxSpan) continue;
                                    const t = child.textContent.trim();
                                    if (t && t.length >= 1 && t.length < 100) {
                                        label = t;
                                        break;
                                    }
                                }
                            }
                        }
                    }

                    // 4. Parent label wrapper (direct)
                    if (!label) {
                        const p = cb.parentElement;
                        if (p && p.tagName === 'LABEL') {
                            // Exclude the checkbox input's own text, get sibling text
                            for (const child of p.children) {
                                if (child.contains(cb)) continue;
                                const t = child.textContent.trim();
                                if (t && t.length >= 1 && t.length < 100) {
                                    label = t;
                                    break;
                                }
                            }
                        }
                    }

                    // 5. Check grandparent for label children
                    if (!label) {
                        const gp = cb.parentElement ? cb.parentElement.parentElement : null;
                        if (gp) {
                            for (const child of gp.children) {
                                if (child.contains(cb)) continue;
                                const t = child.textContent.trim();
                                if (t && t.length >= 1 && t.length < 100) {
                                    label = t;
                                    break;
                                }
                            }
                        }
                    }

                    // 6. Walk up and look for text in any ancestor's children
                    if (!label) {
                        let walk = cb.parentElement;
                        for (let j = 0; j < 5; j++) {
                            if (!walk || walk === document.body) break;
                            for (const child of walk.children) {
                                if (child.contains(cb)) continue;
                                const t = child.textContent.trim();
                                if (t && t.length >= 1 && t.length < 100 && !/^[0-9\\s.]+$/.test(t)) {
                                    label = t;
                                    break;
                                }
                            }
                            if (label) break;
                            walk = walk.parentElement;
                        }
                    }

                    // 7. Fallback: value attribute
                    if (!label || label.length > 100) {
                        label = cb.getAttribute('value') || ('选项' + (idx + 1));
                    }
                    const needs_text = /(?:其它|其他|请注明|请说明|请填写|other|specify)/i.test(label);
                    return {
                        label: label,
                        has_text_input: needs_text,
                    };
                });

                return {title: title, options: options, input_type: 'checkbox'};
            });
        }"""
    )


def get_checkbox_groups(page: Page) -> dict[str, list[Locator]]:
    """Get checkbox groups for form-filling, grouped by form-item container."""
    checkbox_inputs = page.locator('input[type="checkbox"]').all()
    if not checkbox_inputs:
        return {}

    # Use container-based grouping (same logic as radio groups)
    groups: dict[str, list[Locator]] = {}
    for cb in checkbox_inputs:
        try:
            # Find the nearest ant-form-item ancestor
            form_item = cb.locator("xpath=ancestor::*[contains(@class, 'ant-form-item')][1]")
            if form_item.count() > 0:
                # Get a stable identifier from the form item's DOM position
                key = cb.evaluate(
                    """(el) => {
                        let walk = el.parentElement;
                        for (let i = 0; i < 6; i++) {
                            if (!walk || walk === document.body) break;
                            if (/\\bant-form-item\\b/.test(walk.className || '')) {
                                const items = Array.from(document.querySelectorAll('.ant-form-item'));
                                return 'cb.fi.' + items.indexOf(walk);
                            }
                            walk = walk.parentElement;
                        }
                        return 'cb.loose';
                    }"""
                )
            else:
                continue  # Skip checkboxes not in form items
        except Exception:
            continue

        if key not in groups:
            groups[key] = []
        groups[key].append(cb)

    return groups
