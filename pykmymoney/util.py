
from decimal import Decimal


def kmmvalue_to_decimal(kmmvalue: str) -> Decimal:
    """Translate a decimal value in string format to a Decimal.

    Examples:
        >>> kmmvalue_to_decimal('2385/100')
        Decimal('23.85')
        >>> kmmvalue_to_decimal('0/1')
        Decimal('0')
    """
    n, d = kmmvalue.split('/')
    return Decimal(n) / Decimal(d)
