import datetime
import json
import os
import os.path
import sys
from typing import Dict, Tuple

import click
import pandas as pd
from pyproj import Proj

import fire.cli
from fire.cli import firedb
from fire.api.model import (
    Point,
    Punkt,
    Sag,
)


# ------------------------------------------------------------------------------
@click.group()
def gnss():
    """GNSS: basal koordinatilægning
    """
    pass


# ------------------------------------------------------------------------------
# Regnearksdefinitioner (søjlenavne og -typer)
# ------------------------------------------------------------------------------

ARKDEF_FILOVERSIGT = {"Filnavn": str, "Type": str, "σ": float, "δ": float}

ARKDEF_KOORDINATER = {
    "Punkt": str,
    "System": str,
    "x": float,
    "y": float,
    "z": float,
    "t": float,
    "σx": float,
    "σy": float,
    "σz": float,
    "σt": float,
    "uuid": str,
}

# ------------------------------------------------------------------------------
# Hjælpefunktioner
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
def anvendte(arkdef: Dict) -> str:
    """Anvendte søjler for given arkdef"""
    n = len(arkdef)
    if (n < 1) or (n > 26):
        return ""
    return "A:" + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n - 1]


# -----------------------------------------------------------------------------
def skriv_ark(
    projektnavn: str, resultater: Dict[str, pd.DataFrame], suffix: str = "-resultat"
) -> None:
    """Skriv resultater til excel-fil"""

    filnavn = f"{projektnavn}{suffix}.xlsx"
    if suffix != "":
        fire.cli.print(f"Skriver: {tuple(resultater)}")
        fire.cli.print(f"Til filen '{filnavn}'")

    writer = pd.ExcelWriter(filnavn, engine="xlsxwriter")
    for r in resultater:
        resultater[r].to_excel(writer, sheet_name=r, encoding="utf-8", index=False)

    # Giv brugeren en chance for at lukke et åbent regneark
    while True:
        try:
            writer.save()
            if suffix == "-resultat":
                os.startfile(f"{projektnavn}-resultat.xlsx")
            return
        except:
            fire.cli.print(
                f"Kan ikke skrive til '{filnavn}' - måske fordi den er åben.",
                fg="yellow",
                bold=True,
            )
            if input("Prøv igen ([j]/n)? ") in ["j", "J", "ja", ""]:
                continue
            fire.cli.print("Dropper skrivning")
            return


# ------------------------------------------------------------------------------
def find_faneblad(
    projektnavn: str, faneblad: str, arkdef: Dict, ignore_failure: bool = False
) -> pd.DataFrame:
    try:
        return pd.read_excel(
            f"{projektnavn}.xlsx",
            sheet_name=faneblad,
            usecols=anvendte(arkdef),
        ).astype(arkdef)
    except Exception as ex:
        if ignore_failure:
            return None
        fire.cli.print(f"Kan ikke læse {faneblad} fra '{projektnavn}.xlsx'")
        fire.cli.print(
            f"- har du glemt at kopiere den fra '{projektnavn}-resultat.xlsx'?"
        )
        fire.cli.print(f"Anden mulig årsag: {ex}")
        sys.exit(1)

# -----------------------------------------------------------------------------
def find_sag(projektnavn: str) -> Sag:
    """Bomb hvis sag for projektnavn ikke er oprettet. Ellers returnér sagen"""
    sagsgang = find_sagsgang(projektnavn)
    sagsid = find_sagsid(sagsgang)
    try:
        sag = firedb.hent_sag(sagsid)
    except:
        fire.cli.print(
            f" Sag for {projektnavn} er endnu ikke oprettet - brug fire niv opret-sag! ",
            bold=True,
            bg="red",
        )
        sys.exit(1)
    if not sag.aktiv:
        fire.cli.print(
            f"Sag {sagsid} for {projektnavn} er markeret inaktiv. Genåbn for at gå videre."
        )
        sys.exit(1)
    return sag


# ------------------------------------------------------------------------------
def find_sagsgang(projektnavn: str) -> pd.DataFrame:
    """Udtræk sagsgangsregneark fra Excelmappe"""
    return pd.read_excel(f"{projektnavn}.xlsx", sheet_name="Sagsgang")


# ------------------------------------------------------------------------------
def find_sagsid(sagsgang: pd.DataFrame) -> str:
    sag = sagsgang.index[sagsgang["Hændelse"] == "sagsoprettelse"].tolist()
    assert (
        len(sag) == 1
    ), "Der skal være præcis 1 hændelse af type sagsoprettelse i arket"
    i = sag[0]
    if not pd.isna(sagsgang.uuid[i]):
        return str(sagsgang.uuid[i])
    return ""


def bekræft(spørgsmål: str, alvor: bool, test: bool) -> Tuple[bool, bool]:
    """Sikkerhedsdialog: Undgå uønsket skrivning til databasen"""
    # Påtving konsistens mellem alvor/test flag
    if not alvor:
        test = True
        fire.cli.print(f"TESTER '{spørgsmål}'", fg="yellow", bold=True)
        return alvor, test
    else:
        test = False

    # Fortrydelse?: returner inkonsistent tilstand, alvor = test = True
    fire.cli.print(f" BEKRÆFT: {spørgsmål}? ", bg="red", fg="white")
    if "ja" != input("OK (ja/nej)? "):
        fire.cli.print(f"DROPPER '{spørgsmål}'")
        return True, True

    # Bekræftelse
    fire.cli.print(f"UDFØRER '{spørgsmål}'")
    return alvor, test


from .ilæg_nye_koordinater import ilæg_nye_koordinater

