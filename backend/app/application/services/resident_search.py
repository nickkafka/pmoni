"""
Finding a resident by hand, for when the face was not recognised.

The porter has someone standing in front of them and needs an answer in seconds:
who is this, and which apartment. They may have a name spoken out loud, a document
in hand, or just the apartment the person claims — so one field accepts all three.

Matching runs in Python rather than in SQL because the useful comparisons are not
the ones a database does by default: "joao" has to find "João", and a document
typed as 12345678900 has to find one stored as 123.456.789-00. A condominium
directory is small enough that reading it and filtering here costs nothing.
"""

import unicodedata
from collections.abc import Iterable

from app.domain.entities.resident import DirectoryPerson, Resident

MINIMUM_QUERY = 2
"""Shorter than this matches most of the building, which is not an answer."""

DEFAULT_LIMIT = 20

LOCATION_PREFIX = "-"
"""
Marks a search for an apartment or a block instead of a person.

Apartments here are often a bare number, and some are a single digit. Typed on their
own they are unusable: "1" is below the minimum, and "12" reaches every document
containing those digits. The dash says which field is meant, which both makes one
character enough and keeps the answer to the apartments.
"""


def fold(text: str) -> str:
    """Strip case and accents, so what the porter types matches how it was spelled."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def digits_of(text: str | None) -> str:
    """Keep only digits, so punctuation in a document never decides a match."""
    return "".join(c for c in text if c.isdigit()) if text else ""


def group_people(enrollments: Iterable[Resident]) -> list[DirectoryPerson]:
    """Collapse the enrollments of one person into a single entry.

    Identifier and name together, never the identifier alone: devices enrolled
    separately reuse numbers for different people (ADR 0010).
    """
    people: dict[tuple[str, str], dict] = {}
    for enrollment in enrollments:
        key = (enrollment.employee_no, enrollment.name)
        person = people.get(key)
        if person is None:
            person = {
                "employee_no": enrollment.employee_no,
                "name": enrollment.name,
                "apartment": None,
                "block": None,
                "cpf": None,
                "rg": None,
                "photo_id": None,
                "device_ids": [],
            }
            people[key] = person
        person["apartment"] = person["apartment"] or enrollment.apartment
        person["block"] = person["block"] or enrollment.block
        person["cpf"] = person["cpf"] or enrollment.cpf
        person["rg"] = person["rg"] or enrollment.rg
        # Stable across calls, so the same face keeps showing up for the same person.
        if enrollment.has_photo and person["photo_id"] is None:
            person["photo_id"] = enrollment.id
        person["device_ids"].append(enrollment.device_id)

    return [
        DirectoryPerson(
            employee_no=person["employee_no"],
            name=person["name"],
            apartment=person["apartment"],
            block=person["block"],
            cpf=person["cpf"],
            rg=person["rg"],
            photo_id=person["photo_id"],
            device_ids=tuple(sorted(set(person["device_ids"]))),
        )
        for person in people.values()
    ]


def _rank(person: DirectoryPerson, folded_query: str, query_digits: str) -> int | None:
    """Position of a person in the results, or ``None`` when they do not match.

    Lower comes first: an exact apartment is almost certainly the intended answer,
    a name that starts with what was typed is the next best, and the rest follow.
    """
    apartment = fold(person.apartment or "")
    if query_digits and apartment and apartment == fold(query_digits):
        return 0

    name = fold(person.name)
    if name.startswith(folded_query):
        return 1

    # Every word has to appear, so "joao silva" finds "João da Silva" while still
    # ruling out the other Joãos.
    terms = folded_query.split()
    if terms and all(term in name for term in terms):
        return 2

    if query_digits:
        # Qualquer um dos dois documentos serve: o porteiro lê o que a pessoa tem na
        # mão, e não escolhe qual ela vai apresentar.
        if any(query_digits in digits_of(documento) for documento in (person.cpf, person.rg)):
            return 3
        if apartment.startswith(fold(query_digits)):
            return 4

    return None


def _rank_location(person: DirectoryPerson, wanted: str) -> int | None:
    """Where a person sits in a search written as ``-<apartamento ou bloco>``."""
    apartment = fold(person.apartment or "")
    block = fold(person.block or "")
    if apartment and apartment == wanted:
        return 0
    if block and block == wanted:
        return 1
    # Last, and only as a prefix: "-13" sweeping the thirteenth floor is useful,
    # while "-1" answering with 1204 is the noise the dash exists to remove.
    if apartment.startswith(wanted):
        return 2
    return None


def search_location(
    enrollments: Iterable[Resident], term: str, *, limit: int = DEFAULT_LIMIT
) -> list[DirectoryPerson]:
    """Everyone in an apartment or a block, however short its name."""
    wanted = fold(term)
    if not wanted:
        return []

    ranked = [
        (rank, fold(person.name), person)
        for person in group_people(enrollments)
        if (rank := _rank_location(person, wanted)) is not None
    ]
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [person for _, _, person in ranked[:limit]]


def search(
    enrollments: Iterable[Resident], query: str, *, limit: int = DEFAULT_LIMIT
) -> list[DirectoryPerson]:
    """People matching a name, a document or an apartment, best guess first."""
    raw = query.strip()
    if raw.startswith(LOCATION_PREFIX):
        return search_location(enrollments, raw[len(LOCATION_PREFIX):], limit=limit)

    folded_query = fold(query)
    if len(folded_query) < MINIMUM_QUERY:
        return []
    query_digits = digits_of(query)

    ranked = []
    for person in group_people(enrollments):
        rank = _rank(person, folded_query, query_digits)
        if rank is not None:
            ranked.append((rank, fold(person.name), person))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [person for _, _, person in ranked[:limit]]
