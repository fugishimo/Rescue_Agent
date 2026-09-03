from datetime import date

from fastapi.testclient import TestClient

from app.data.profiles import LISTERS, RENTERS
from app.data.seed_data import BOOKINGS, EVENTS, LISTINGS, validate_seed_relationships
from app.main import app


client = TestClient(app)


def test_exact_profile_catalog() -> None:
    assert len(RENTERS) == 6
    assert len(LISTERS) == 5
    assert len(RENTERS) + len(LISTERS) == 11
    assert {renter.name for renter in RENTERS} == {
        "Maya Rodriguez",
        "Alex Kim",
        "Jordan Patel",
        "Emily Nguyen",
        "Marcus Lee",
        "Sofia Martinez",
    }
    assert {lister.name for lister in LISTERS} == {
        "Sarah Chen",
        "David Brooks",
        "Priya Shah",
        "Andre Williams",
        "Olivia Park",
    }
    assert len({profile.id for profile in (*RENTERS, *LISTERS)}) == 11


def test_profile_probabilities_and_ranges_match_specification() -> None:
    renters = {renter.id: renter for renter in RENTERS}
    listers = {lister.id: lister for lister in LISTERS}

    assert renters["renter_maya"].views_before_action.model_dump() == {
        "minimum": 4,
        "maximum": 7,
    }
    assert renters["renter_alex"].checkout_abandonment_rate == 0.65
    assert renters["renter_jordan"].payment_failure_rate == 0.55
    assert renters["renter_emily"].payment_failure_rate == 0.02
    assert renters["renter_marcus"].sms_response_rate == 0.40
    assert renters["renter_sofia"].post_confirmation_inactivity_rate == 0.55

    assert listers["lister_sarah"].average_response_minutes == 4
    assert listers["lister_david"].average_response_minutes == 25
    assert listers["lister_priya"].availability_confirmation_rate == 0.55
    assert listers["lister_andre"].missed_app_notification_rate == 0.50
    assert listers["lister_olivia"].acceptance_rate == 0.55


def test_all_listings_have_valid_owners() -> None:
    lister_ids = {lister.id for lister in LISTERS}
    listing_owner_ids = {listing.lister_id for listing in LISTINGS}

    assert len(LISTINGS) == 11
    assert listing_owner_ids == lister_ids
    assert all(listing.lister_id in lister_ids for listing in LISTINGS)


def test_seed_booking_relationships_and_profile_ranges() -> None:
    renters = {renter.id: renter for renter in RENTERS}
    listings = {listing.id: listing for listing in LISTINGS}

    validate_seed_relationships()

    for booking in BOOKINGS:
        renter = renters[booking.renter_id]
        listing = listings[booking.listing_id]
        move_in_days = (booking.move_in - date(2026, 9, 2)).days

        assert listing.lister_id == booking.lister_id
        assert renter.booking_value_range.minimum <= booking.booking_value
        assert booking.booking_value <= renter.booking_value_range.maximum
        assert renter.move_in_days_range.minimum <= move_in_days
        assert move_in_days <= renter.move_in_days_range.maximum


def test_seed_events_reference_existing_bookings() -> None:
    booking_ids = {booking.id for booking in BOOKINGS}

    assert EVENTS
    assert all(event.booking_id in booking_ids for event in EVENTS)


def test_marketplace_endpoints_return_structured_seed_data() -> None:
    profiles_response = client.get("/profiles")
    listings_response = client.get("/listings")
    bookings_response = client.get("/bookings")
    events_response = client.get("/events")
    seed_response = client.get("/marketplace/seed")

    assert profiles_response.status_code == 200
    assert profiles_response.json()["total"] == 11
    assert len(profiles_response.json()["renters"]) == 6
    assert len(profiles_response.json()["listers"]) == 5
    assert listings_response.status_code == 200
    assert len(listings_response.json()) == 11
    assert bookings_response.status_code == 200
    assert len(bookings_response.json()) == 6
    assert events_response.status_code == 200
    assert len(events_response.json()) == len(EVENTS)
    assert seed_response.status_code == 200
    assert seed_response.json()["rescue_actions"] == []
