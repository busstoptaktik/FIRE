from fireapi.model import *


def test_hent_alle_punktinformationtyper(firedb):
    all = list(firedb.hent_punktinformationtyper())
    assert len(all) > 0


def test_hent_punktinformationtyper_for_namespace(firedb):
    all = list(firedb.hent_punktinformationtyper())
    filter = list(firedb.hent_punktinformationtyper(namespace="AFM"))
    assert len(all) > len(filter)