# -*- coding: utf-8 -*-
"""
Главный модуль календаря — объединяет все 4 четверти года в один словарь HOLIDAYS.
"""
from holidays_q1 import HOLIDAYS_Q1
from holidays_q2 import HOLIDAYS_Q2
from holidays_q3 import HOLIDAYS_Q3
from holidays_q4 import HOLIDAYS_Q4

HOLIDAYS = {}
HOLIDAYS.update(HOLIDAYS_Q1)
HOLIDAYS.update(HOLIDAYS_Q2)
HOLIDAYS.update(HOLIDAYS_Q3)
HOLIDAYS.update(HOLIDAYS_Q4)
