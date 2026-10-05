"""
ScholarPath matching engine — actual inverted index + actual AST evaluator.

Replaces the linear-scan `build_inverted_index()` and flat-dict
`evaluate_ast()` in app.py with structures that match their names.
"""

from collections import defaultdict


# ── INVERTED INDEX ────────────────────────────────────────────────────────
# Maps (field, value) -> set of scholarship ids that allow that value.
# 'Any' scholarships are stored under a wildcard bucket and always included.

class InvertedIndex:
    FIELDS = ['caste', 'state', 'gender', 'stream', 'area']

    def __init__(self, scholarships):
        self.index = defaultdict(set)          # (field, value) -> {scholarship_id, ...}
        self.wildcard = defaultdict(set)        # field -> {scholarship_id, ...} where field == 'Any' or unset
        self.by_id = {s.id: s for s in scholarships}
        self._build(scholarships)

    def _split(self, raw):
        return [v.strip() for v in raw.split(',')] if raw else []

    def _build(self, scholarships):
        field_map = {
            'caste': 'allowed_caste',
            'state': 'allowed_states',
            'gender': 'allowed_gender',
            'stream': 'allowed_stream',
            'area': 'allowed_area',
        }
        for s in scholarships:
            for field, attr in field_map.items():
                raw = getattr(s, attr)
                values = self._split(raw)
                if not values or 'Any' in values:
                    self.wildcard[field].add(s.id)
                else:
                    for v in values:
                        self.index[(field, v)].add(s.id)

    def candidates(self, student):
        """
        Intersect per-field candidate sets to get a shortlist.
        This is the actual O(1)-per-key lookup + set intersection step —
        no scan over every scholarship.
        """
        student_values = {
            'caste': student.caste,
            'state': student.state,
            'gender': student.gender,
            'stream': student.stream,
            'area': student.area,
        }

        result_ids = None
        for field, value in student_values.items():
            bucket = set(self.wildcard[field])
            if value:
                bucket |= self.index.get((field, value), set())
            result_ids = bucket if result_ids is None else (result_ids & bucket)

        # income and marks aren't indexed as discrete keys (they're ranges,
        # not exact matches) — still cheaper to check as a final filter
        # over the shortlist than as the seed of the intersection.
        shortlist = [self.by_id[i] for i in result_ids] if result_ids else []
        return [
            s for s in shortlist
            if (not s.max_income or not student.income or student.income <= s.max_income)
            and (not s.min_marks or (student.marks and student.marks >= s.min_marks))
        ]


# ── AST ────────────────────────────────────────────────────────────────────
# Real expression tree: Leaf comparisons composed with And / Or / Not nodes.
# Each node returns (bool, explanation) so the UI can show why a match
# succeeded or failed, criterion by criterion.

class Node:
    def evaluate(self, student):
        raise NotImplementedError


class Leaf(Node):
    def __init__(self, label, check_fn):
        self.label = label
        self.check_fn = check_fn

    def evaluate(self, student):
        passed = self.check_fn(student)
        return passed, {'type': 'leaf', 'label': self.label, 'passed': passed}


class And(Node):
    def __init__(self, *children):
        self.children = children

    def evaluate(self, student):
        results = [c.evaluate(student) for c in self.children]
        passed = all(r[0] for r in results)
        return passed, {'type': 'and', 'passed': passed, 'children': [r[1] for r in results]}


class Or(Node):
    def __init__(self, *children):
        self.children = children

    def evaluate(self, student):
        results = [c.evaluate(student) for c in self.children]
        passed = any(r[0] for r in results)
        return passed, {'type': 'or', 'passed': passed, 'children': [r[1] for r in results]}


class Not(Node):
    def __init__(self, child):
        self.child = child

    def evaluate(self, student):
        passed_child, sub = self.child.evaluate(student)
        passed = not passed_child
        return passed, {'type': 'not', 'passed': passed, 'child': sub}


def build_rule_ast(scholarship):
    """
    Builds an actual tree for a scholarship's eligibility rule:
    top-level AND of per-field checks; multi-valued fields (comma-separated
    caste/state/stream lists) become an OR of equality leaves underneath.
    """
    branches = []

    def multi_or(field_label, raw_value, get_student_value):
        values = [v.strip() for v in raw_value.split(',')] if raw_value else []
        if not values or 'Any' in values:
            return Leaf(f'{field_label}: Any', lambda st: True)
        if len(values) == 1:
            v = values[0]
            return Leaf(f'{field_label} = {v}', lambda st, v=v: get_student_value(st) == v)
        leaves = [
            Leaf(f'{field_label} = {v}', lambda st, v=v: get_student_value(st) == v)
            for v in values
        ]
        return Or(*leaves)

    branches.append(multi_or('Caste', scholarship.allowed_caste, lambda st: st.caste))
    branches.append(multi_or('State', scholarship.allowed_states, lambda st: st.state))
    branches.append(multi_or('Stream', scholarship.allowed_stream, lambda st: st.stream))

    if scholarship.allowed_gender and scholarship.allowed_gender != 'Any':
        g = scholarship.allowed_gender
        branches.append(Leaf(f'Gender = {g}', lambda st, g=g: st.gender == g))

    if scholarship.allowed_area and scholarship.allowed_area != 'Any':
        a = scholarship.allowed_area
        branches.append(Leaf(f'Area = {a}', lambda st, a=a: st.area == a))

    if scholarship.max_income:
        limit = scholarship.max_income
        branches.append(Leaf(
            f'Income ≤ {limit}',
            lambda st, limit=limit: bool(st.income) and st.income <= limit
        ))

    if scholarship.min_marks:
        floor = scholarship.min_marks
        branches.append(Leaf(
            f'Marks ≥ {floor}',
            lambda st, floor=floor: bool(st.marks) and st.marks >= floor
        ))

    if scholarship.disability_required is not None:
        req = scholarship.disability_required
        branches.append(Leaf(
            f'Disability required: {req}',
            lambda st, req=req: st.disability == req
        ))

    return And(*branches) if branches else Leaf('No criteria', lambda st: True)


def evaluate_ast(scholarship, student):
    """Drop-in replacement for the old flat-dict version — same call signature."""
    tree = build_rule_ast(scholarship)
    passed, explanation = tree.evaluate(student)
    return passed, explanation


def match_scholarships(student, all_scholarships, index=None):
    """
    Drop-in replacement for the old match_scholarships().
    Phase 1: inverted index shortlist. Phase 2: AST evaluation + explanation.
    Returns list of (scholarship, explanation) tuples.
    """
    idx = index or InvertedIndex(all_scholarships)
    shortlist = idx.candidates(student)

    matches = []
    for s in shortlist:
        passed, explanation = evaluate_ast(s, student)
        if passed:
            matches.append((s, explanation))
    return matches
