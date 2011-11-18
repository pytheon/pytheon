# -*- coding: utf-8 -*-
import os
import sys
import pkg_resources

# load entry points from debian extra directories
for d in [p for p in sys.path if '/python' in p]:
    if os.path.isdir(d) and d not in pkg_resources.working_set.entries:
        pkg_resources.working_set.add_entry(d)

# load entry points from extra eggs
for p in sys.path:
    if p.endswith('.egg') and p not in pkg_resources.working_set.entries:
        pkg_resources.working_set.add_entry(p)


