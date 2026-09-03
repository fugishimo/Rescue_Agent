from datetime import date, datetime, timezone

from app.data.profiles import LISTERS, RENTERS
from app.models import (
    AvailabilityStatus,
    Booking,
    BookingStatus,
    Event,
    EventType,
    Lister,
    Listing,
    Market,
    Renter,
    RescueAction,
)
from app.models.common import DomainModel


SEED_REFERENCE_TIME = datetime(2026, 9, 2, 18, 0, tzinfo=timezone.utc)


LISTINGS: tuple[Listing, ...] = (
    Listing(
        id="listing_williamsburg_loft",
        lister_id="lister_sarah",
        name="Williamsburg Loft",
        market=Market.BROOKLYN,
        monthly_price=2400,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_greenpoint_studio",
        lister_id="lister_sarah",
        name="Greenpoint Studio",
        market=Market.BROOKLYN,
        monthly_price=2150,
        availability_status=AvailabilityStatus.AVAILABLE,
    ),
    Listing(
        id="listing_soho_studio",
        lister_id="lister_david",
        name="SoHo Studio",
        market=Market.MANHATTAN,
        monthly_price=3300,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_lower_east_side_room",
        lister_id="lister_david",
        name="Lower East Side Room",
        market=Market.MANHATTAN,
        monthly_price=2100,
        availability_status=AvailabilityStatus.AVAILABLE,
    ),
    Listing(
        id="listing_chelsea_furnished_room",
        lister_id="lister_priya",
        name="Chelsea Furnished Room",
        market=Market.MANHATTAN,
        monthly_price=2750,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_east_village_studio",
        lister_id="lister_priya",
        name="East Village Studio",
        market=Market.MANHATTAN,
        monthly_price=3050,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_bushwick_creative_loft",
        lister_id="lister_andre",
        name="Bushwick Creative Loft",
        market=Market.BROOKLYN,
        monthly_price=2000,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_bed_stuy_brownstone_room",
        lister_id="lister_andre",
        name="Bed-Stuy Brownstone Room",
        market=Market.BROOKLYN,
        monthly_price=1850,
        availability_status=AvailabilityStatus.AVAILABLE,
    ),
    Listing(
        id="listing_crown_heights_studio",
        lister_id="lister_andre",
        name="Crown Heights Studio",
        market=Market.BROOKLYN,
        monthly_price=2250,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_astoria_apartment",
        lister_id="lister_olivia",
        name="Astoria Apartment",
        market=Market.QUEENS,
        monthly_price=2300,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
    Listing(
        id="listing_long_island_city_studio",
        lister_id="lister_olivia",
        name="Long Island City Studio",
        market=Market.QUEENS,
        monthly_price=2900,
        availability_status=AvailabilityStatus.UNCONFIRMED,
    ),
)


BOOKINGS: tuple[Booking, ...] = (
    Booking(
        id="booking_maya_williamsburg",
        renter_id="renter_maya",
        lister_id="lister_sarah",
        listing_id="listing_williamsburg_loft",
        move_in=date(2026, 9, 6),
        move_out=date(2026, 10, 6),
        booking_value=2400,
        status=BookingStatus.BOOKING_REQUESTED,
        created_at=datetime(2026, 9, 2, 17, 40, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 48, tzinfo=timezone.utc),
    ),
    Booking(
        id="booking_alex_soho",
        renter_id="renter_alex",
        lister_id="lister_david",
        listing_id="listing_soho_studio",
        move_in=date(2026, 9, 16),
        move_out=date(2026, 10, 16),
        booking_value=3300,
        status=BookingStatus.CHECKOUT_STARTED,
        created_at=datetime(2026, 9, 2, 17, 34, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 52, tzinfo=timezone.utc),
    ),
    Booking(
        id="booking_jordan_chelsea",
        renter_id="renter_jordan",
        lister_id="lister_priya",
        listing_id="listing_chelsea_furnished_room",
        move_in=date(2026, 9, 9),
        move_out=date(2026, 10, 9),
        booking_value=2750,
        status=BookingStatus.BOOKING_REQUESTED,
        created_at=datetime(2026, 9, 2, 17, 38, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 55, tzinfo=timezone.utc),
    ),
    Booking(
        id="booking_emily_greenpoint",
        renter_id="renter_emily",
        lister_id="lister_sarah",
        listing_id="listing_greenpoint_studio",
        move_in=date(2026, 9, 23),
        move_out=date(2026, 10, 23),
        booking_value=2150,
        status=BookingStatus.INQUIRY,
        created_at=datetime(2026, 9, 2, 17, 28, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 46, tzinfo=timezone.utc),
    ),
    Booking(
        id="booking_marcus_astoria",
        renter_id="renter_marcus",
        lister_id="lister_olivia",
        listing_id="listing_astoria_apartment",
        move_in=date(2026, 10, 2),
        move_out=date(2026, 11, 2),
        booking_value=2300,
        status=BookingStatus.BROWSING,
        created_at=datetime(2026, 9, 2, 17, 20, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 58, tzinfo=timezone.utc),
    ),
    Booking(
        id="booking_sofia_bushwick",
        renter_id="renter_sofia",
        lister_id="lister_andre",
        listing_id="listing_bushwick_creative_loft",
        move_in=date(2026, 9, 12),
        move_out=date(2026, 10, 12),
        booking_value=2000,
        status=BookingStatus.AWAITING_AVAILABILITY,
        created_at=datetime(2026, 9, 2, 17, 42, tzinfo=timezone.utc),
        last_activity_at=datetime(2026, 9, 2, 17, 57, tzinfo=timezone.utc),
    ),
)


EVENTS: tuple[Event, ...] = (
    Event(
        id="event_maya_viewed",
        booking_id="booking_maya_williamsburg",
        event_type=EventType.LISTING_VIEWED,
        timestamp=datetime(2026, 9, 2, 17, 40, tzinfo=timezone.utc),
        metadata={"view_count": 5},
    ),
    Event(
        id="event_maya_requested",
        booking_id="booking_maya_williamsburg",
        event_type=EventType.BOOKING_REQUESTED,
        timestamp=datetime(2026, 9, 2, 17, 48, tzinfo=timezone.utc),
    ),
    Event(
        id="event_alex_viewed",
        booking_id="booking_alex_soho",
        event_type=EventType.LISTING_VIEWED,
        timestamp=datetime(2026, 9, 2, 17, 34, tzinfo=timezone.utc),
        metadata={"view_count": 7},
    ),
    Event(
        id="event_alex_checkout",
        booking_id="booking_alex_soho",
        event_type=EventType.BOOKING_STARTED,
        timestamp=datetime(2026, 9, 2, 17, 52, tzinfo=timezone.utc),
    ),
    Event(
        id="event_jordan_inquiry",
        booking_id="booking_jordan_chelsea",
        event_type=EventType.INQUIRY_SENT,
        timestamp=datetime(2026, 9, 2, 17, 38, tzinfo=timezone.utc),
    ),
    Event(
        id="event_jordan_requested",
        booking_id="booking_jordan_chelsea",
        event_type=EventType.BOOKING_REQUESTED,
        timestamp=datetime(2026, 9, 2, 17, 55, tzinfo=timezone.utc),
    ),
    Event(
        id="event_emily_viewed",
        booking_id="booking_emily_greenpoint",
        event_type=EventType.LISTING_VIEWED,
        timestamp=datetime(2026, 9, 2, 17, 28, tzinfo=timezone.utc),
        metadata={"view_count": 4},
    ),
    Event(
        id="event_emily_inquiry",
        booking_id="booking_emily_greenpoint",
        event_type=EventType.INQUIRY_SENT,
        timestamp=datetime(2026, 9, 2, 17, 46, tzinfo=timezone.utc),
    ),
    Event(
        id="event_marcus_viewed",
        booking_id="booking_marcus_astoria",
        event_type=EventType.LISTING_VIEWED,
        timestamp=datetime(2026, 9, 2, 17, 58, tzinfo=timezone.utc),
        metadata={"view_count": 9},
    ),
    Event(
        id="event_sofia_requested",
        booking_id="booking_sofia_bushwick",
        event_type=EventType.BOOKING_REQUESTED,
        timestamp=datetime(2026, 9, 2, 17, 42, tzinfo=timezone.utc),
    ),
    Event(
        id="event_sofia_availability",
        booking_id="booking_sofia_bushwick",
        event_type=EventType.AVAILABILITY_REQUESTED,
        timestamp=datetime(2026, 9, 2, 17, 57, tzinfo=timezone.utc),
    ),
)


RESCUE_ACTIONS: tuple[RescueAction, ...] = ()


class ProfileCatalog(DomainModel):
    renters: tuple[Renter, ...]
    listers: tuple[Lister, ...]
    total: int


class MarketplaceSeed(DomainModel):
    reference_time: datetime
    renters: tuple[Renter, ...]
    listers: tuple[Lister, ...]
    listings: tuple[Listing, ...]
    bookings: tuple[Booking, ...]
    events: tuple[Event, ...]
    rescue_actions: tuple[RescueAction, ...]


def validate_seed_relationships() -> None:
    renter_ids = {renter.id for renter in RENTERS}
    lister_ids = {lister.id for lister in LISTERS}
    listings_by_id = {listing.id: listing for listing in LISTINGS}
    booking_ids = {booking.id for booking in BOOKINGS}

    if len(RENTERS) != 6 or len(LISTERS) != 5:
        raise ValueError("seed data must contain exactly 6 renters and 5 listers")

    for listing in LISTINGS:
        if listing.lister_id not in lister_ids:
            raise ValueError(f"listing {listing.id} references an unknown lister")

    for booking in BOOKINGS:
        listing = listings_by_id.get(booking.listing_id)
        if booking.renter_id not in renter_ids:
            raise ValueError(f"booking {booking.id} references an unknown renter")
        if booking.lister_id not in lister_ids:
            raise ValueError(f"booking {booking.id} references an unknown lister")
        if listing is None:
            raise ValueError(f"booking {booking.id} references an unknown listing")
        if listing.lister_id != booking.lister_id:
            raise ValueError(f"booking {booking.id} does not match the listing owner")

    for event in EVENTS:
        if event.booking_id not in booking_ids:
            raise ValueError(f"event {event.id} references an unknown booking")

    for action in RESCUE_ACTIONS:
        if action.booking_id not in booking_ids:
            raise ValueError(f"rescue action {action.id} references an unknown booking")


validate_seed_relationships()


PROFILE_CATALOG = ProfileCatalog(
    renters=RENTERS,
    listers=LISTERS,
    total=len(RENTERS) + len(LISTERS),
)

MARKETPLACE_SEED = MarketplaceSeed(
    reference_time=SEED_REFERENCE_TIME,
    renters=RENTERS,
    listers=LISTERS,
    listings=LISTINGS,
    bookings=BOOKINGS,
    events=EVENTS,
    rescue_actions=RESCUE_ACTIONS,
)
