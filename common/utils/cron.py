"""
Cron expression parsing utilities
"""
from datetime import datetime
from typing import List, Set, Tuple

def parse_cron_field(field: str, min_val: int, max_val: int) -> Set[int]:
    """
    Parse a generic cron field (minute, hour, etc.)
    
    Supports:
    - * : all values
    - */n : step values
    - n,m : list of values
    - n-m : range of values
    """
    if field == '*': 
        return set(range(min_val, max_val + 1))
    
    values = set()
    for part in field.split(','):
        step = 1
        if '/' in part: 
            part, step = part.split('/')
            step = int(step)
        
        if '-' in part: 
            start, end = map(int, part.split('-'))
        elif part == '*': 
            start, end = min_val, max_val
        else: 
            start = end = int(part)
        
        values.update(range(start, end + 1, step))
    
    return {v for v in values if min_val <= v <= max_val}

def is_cron_match(cron_expression: str, dt: datetime = None) -> bool:
    """
    Check if the given datetime matches the cron expression.
    Defaults to datetime.now() if dt is not provided.
    
    Cron format: "minute hour day month day_of_week"
    Supports simplified format: "minute hour day month" (assumes * for dow)
    """
    if dt is None:
        dt = datetime.now()
        
    parts = cron_expression.strip().split()
    
    # Pad with * if simplified format
    if len(parts) < 5:
        parts.extend(["*"] * (5 - len(parts)))
        
    # Standard cron fields: minute, hour, day, month, dow
    # We only implement min, hour, day, month checks commonly used
    checks: List[Tuple[str, int, int, int]] = [
        (parts[0], dt.minute, 0, 59),
        (parts[1], dt.hour, 0, 23),
        (parts[2], dt.day, 1, 31),
        (parts[3], dt.month, 1, 12)
    ]
    
    return all(val in parse_cron_field(p, min_v, max_v) for p, val, min_v, max_v in checks)
