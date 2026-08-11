import unittest

from app.application.services.resident_search import group_people, search
from app.domain.entities.resident import Resident


def enrollment(
    resident_id: int,
    device_id: int,
    employee_no: str,
    name: str,
    *,
    apartment: str | None = None,
    block: str | None = None,
    document: str | None = None,
    has_photo: bool = True,
) -> Resident:
    return Resident(
        id=resident_id, device_id=device_id, employee_no=employee_no, name=name,
        apartment=apartment, block=block, has_photo=has_photo, synced_at=None,
        document=document,
    )


class GroupPeopleTests(unittest.TestCase):
    def test_shows_someone_enrolled_on_several_devices_once(self) -> None:
        people = group_people([
            enrollment(1, 1, "7", "Adna Damares"),
            enrollment(2, 2, "7", "Adna Damares"),
            enrollment(3, 3, "7", "Adna Damares"),
        ])

        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].device_ids, (1, 2, 3))

    def test_keeps_apart_people_sharing_an_identifier(self) -> None:
        """O ID 2 nomeia pessoas diferentes em faciais cadastradas à parte (ADR 0010)."""
        people = group_people([
            enrollment(1, 1, "2", "nk"),
            enrollment(2, 2, "2", "naldo"),
        ])

        self.assertEqual({person.name for person in people}, {"nk", "naldo"})

    def test_gathers_what_was_recorded_on_any_enrollment(self) -> None:
        """Apartamento e documento podem ter sido informados em cadastros diferentes."""
        people = group_people([
            enrollment(1, 1, "7", "Adna", apartment="301"),
            enrollment(2, 2, "7", "Adna", document="123.456.789-00"),
        ])

        self.assertEqual(people[0].apartment, "301")
        self.assertEqual(people[0].document, "123.456.789-00")

    def test_borrows_the_picture_from_an_enrollment_that_has_one(self) -> None:
        people = group_people([
            enrollment(1, 1, "7", "Adna", has_photo=False),
            enrollment(2, 2, "7", "Adna", has_photo=True),
        ])

        self.assertEqual(people[0].photo_id, 2)

    def test_reports_no_picture_when_no_enrollment_has_one(self) -> None:
        people = group_people([enrollment(1, 1, "7", "Adna", has_photo=False)])

        self.assertIsNone(people[0].photo_id)


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = [
            enrollment(1, 1, "7", "João da Silva", apartment="301", document="123.456.789-00"),
            enrollment(2, 2, "7", "João da Silva", apartment="301"),
            enrollment(3, 1, "8", "Maria Antônia Souza", apartment="42", document="98765432100"),
            enrollment(4, 1, "9", "Pedro Henrique", apartment="1301"),
        ]

    def names(self, query: str) -> list[str]:
        return [person.name for person in search(self.directory, query)]

    def test_finds_a_name_typed_without_accents(self) -> None:
        """Ninguém digita "Antônia" com acento às pressas."""
        self.assertEqual(self.names("antonia"), ["Maria Antônia Souza"])

    def test_finds_an_accented_name_typed_with_accents(self) -> None:
        self.assertEqual(self.names("João"), ["João da Silva"])

    def test_ignores_case(self) -> None:
        self.assertEqual(self.names("JOAO"), ["João da Silva"])

    def test_matches_every_word_in_any_order_within_the_name(self) -> None:
        self.assertEqual(self.names("souza maria"), ["Maria Antônia Souza"])

    def test_finds_a_document_typed_without_punctuation(self) -> None:
        """O porteiro lê o documento na mão da pessoa, sem os pontos."""
        self.assertEqual(self.names("12345678900"), ["João da Silva"])

    def test_finds_a_document_typed_with_punctuation(self) -> None:
        self.assertEqual(self.names("987.654.321-00"), ["Maria Antônia Souza"])

    def test_finds_the_apartment_typed_whole(self) -> None:
        self.assertEqual(self.names("301"), ["João da Silva"])

    def test_does_not_answer_301_with_1301(self) -> None:
        """Casar por conteúdo encheria "301" de 1301, 2301, 3013 — o porteiro quer o 301."""
        self.assertNotIn("Pedro Henrique", self.names("301"))

    def test_finds_apartments_by_what_they_start_with(self) -> None:
        """Quem digita "13" está varrendo o andar, não procurando um número exato."""
        self.assertEqual(self.names("13"), ["Pedro Henrique"])

    def test_puts_the_exact_apartment_before_a_name_that_also_matches(self) -> None:
        directory = [
            enrollment(1, 1, "1", "Silva", apartment="500"),
            enrollment(2, 1, "2", "500 Reis", apartment="900"),
        ]

        self.assertEqual(
            [person.name for person in search(directory, "500")], ["Silva", "500 Reis"]
        )

    def test_refuses_a_query_too_short_to_mean_anything(self) -> None:
        self.assertEqual(search(self.directory, "a"), [])
        self.assertEqual(search(self.directory, " "), [])

    def test_answers_nothing_when_nobody_matches(self) -> None:
        self.assertEqual(search(self.directory, "zulmira"), [])

    def test_returns_a_person_once_however_many_devices(self) -> None:
        found = search(self.directory, "joao")

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].device_ids, (1, 2))

    def test_stops_at_the_limit(self) -> None:
        crowd = [
            enrollment(index, 1, str(index), f"Ana {index}", apartment=None)
            for index in range(50)
        ]

        self.assertEqual(len(search(crowd, "ana", limit=5)), 5)


class LocationSearchTests(unittest.TestCase):
    """A busca escrita como "-<apartamento ou bloco>"."""

    def setUp(self) -> None:
        self.directory = [
            enrollment(1, 1, "1", "Ana", apartment="1", block="A"),
            enrollment(2, 1, "2", "Bruno", apartment="12", block="A"),
            enrollment(3, 1, "3", "Carla", apartment="1204", block="B"),
            enrollment(4, 1, "4", "Diego", apartment="13", block="B"),
            # Documento contendo "12", para provar que ele não entra nesta busca.
            enrollment(5, 1, "5", "Elza", apartment="900", document="12345678900"),
        ]

    def names(self, query: str) -> list[str]:
        return [person.name for person in search(self.directory, query)]

    def test_finds_an_apartment_of_a_single_digit(self) -> None:
        """"1" sozinho é curto demais para a busca comum; com o traço, encontra."""
        self.assertIn("Ana", self.names("-1"))

    def test_puts_the_exact_apartment_before_the_ones_that_begin_with_it(self) -> None:
        """O 1 exato vem antes de 12, 13 e 1204, que só começam com o que foi digitado."""
        self.assertEqual(self.names("-1")[0], "Ana")
        self.assertEqual(sorted(self.names("-1")[1:]), ["Bruno", "Carla", "Diego"])

    def test_finds_a_block(self) -> None:
        self.assertEqual(self.names("-A"), ["Ana", "Bruno"])

    def test_ignores_case_in_a_block(self) -> None:
        self.assertEqual(self.names("-a"), self.names("-A"))

    def test_never_answers_with_a_document(self) -> None:
        """O traço existe para tirar o documento do caminho de uma busca numérica."""
        self.assertNotIn("Elza", self.names("-12"))

    def test_never_answers_with_a_name(self) -> None:
        self.assertEqual(self.names("-ana"), [])

    def test_sweeps_a_floor_by_prefix(self) -> None:
        self.assertEqual(self.names("-12"), ["Bruno", "Carla"])

    def test_tolerates_a_space_after_the_dash(self) -> None:
        self.assertEqual(self.names("- 13"), ["Diego"])

    def test_answers_nothing_to_a_lone_dash(self) -> None:
        self.assertEqual(self.names("-"), [])

    def test_keeps_someone_out_of_a_block_they_are_not_in(self) -> None:
        self.assertNotIn("Diego", self.names("-A"))


if __name__ == "__main__":
    unittest.main()
