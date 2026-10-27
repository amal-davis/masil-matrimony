"""
Diamond features in this app: the Gold test classes (unlimited interests,
messaging, who viewed my profile, shortlist, and the 100-number contact
allowance at the 1st, 100th and 101st contact, repeats, denials, expiry and
simultaneous requests) run again with a Diamond membership.
"""
from . import tests_gold


class DiamondFeatureTests(tests_gold.GoldFeatureTests):
    PLAN = "diamond"


class DiamondContactAllowanceTests(tests_gold.GoldContactAllowanceTests):
    PLAN = "diamond"


class DiamondConcurrentContactViewTests(tests_gold.GoldConcurrentContactViewTests):
    PLAN = "diamond"
