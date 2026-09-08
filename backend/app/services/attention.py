from app.models import Booking


HIGH_VALUE_THRESHOLD = 4_000


def is_high_value(booking_or_value: Booking | int) -> bool:
    value = (
        booking_or_value.booking_value
        if isinstance(booking_or_value, Booking)
        else booking_or_value
    )
    return value >= HIGH_VALUE_THRESHOLD
