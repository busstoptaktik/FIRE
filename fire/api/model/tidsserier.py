from dataclasses import dataclass, fields
from datetime import datetime as dt
import time
from typing import List, Tuple, Type

import functools
import numpy as np
from numpy.polynomial import polynomial as P
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from scipy.stats import t, norm

from fire.matematik import xyz2neu
from fire.api.model import (
    FikspunktregisterObjekt,
    Observation,
    ObservationsLængde,
    ResidualKovarians,
    KoordinatKovarians,
    tidsserie_koordinat,
)
from fire.api.model.observationer import ObservationsLængde
from fire.api.model.punkttyper import Koordinat

__all__ = [
    "Tidsserie",
    "GNSSTidsserie",
    "HøjdeTidsserie",
]


def til_decimalår(date):
    """
    Stjålet fra StackOverflow og omdøbt:

    https://stackoverflow.com/a/6451892
    """

    def sinceEpoch(date):  # returns seconds since epoch
        return time.mktime(date.timetuple())

    s = sinceEpoch

    year = date.year
    startOfThisYear = dt(year=year, month=1, day=1)
    startOfNextYear = dt(year=year + 1, month=1, day=1)

    yearElapsed = s(date) - s(startOfThisYear)
    yearDuration = s(startOfNextYear) - s(startOfThisYear)
    fraction = yearElapsed / yearDuration

    return date.year + fraction


def beregn_fraktil_for_t_fordeling(q: float, dof: int = 0) -> float:
    """Returner den q'te fraktil for t-fordelingen med dof frihedsgrader."""
    return t.ppf(q, dof)


def beregn_fraktil_for_normalfordeling(q: float) -> float:
    """Returner den q'te fraktil for normalfordelingen."""
    return norm.ppf(q)


class TidsserietypeID:
    """
    ID for eksisterende tidsserietyper i FIRE-databasen.

    Notes
    -----
    ID'erne er fastsat i DDL-filerne for databasen og kan derfor fastsættes her.

    """

    gnss = 1
    højde = 2


class Tidsserie(FikspunktregisterObjekt):
    __tablename__ = "tidsserie"
    sagseventfraid = Column(String, ForeignKey("sagsevent.id"), nullable=False)
    sagsevent = relationship(
        "Sagsevent", foreign_keys=[sagseventfraid], back_populates="tidsserier"
    )
    sagseventtilid = Column(String, ForeignKey("sagsevent.id"), nullable=True)
    slettet = relationship(
        "Sagsevent",
        foreign_keys=[sagseventtilid],
        back_populates="tidsserier_slettede",
    )

    punktid = Column(String(36), ForeignKey("punkt.id"))
    punkt = relationship("Punkt")

    punktsamlingsid = Column(Integer, ForeignKey("punktsamling.objektid"))
    punktsamling = relationship("PunktSamling", back_populates="tidsserier")

    navn = Column(String, nullable=False)
    formål = Column("formaal", String, nullable=False)

    sridid = Column(Integer, ForeignKey("sridtype.sridid"), nullable=False)
    srid = relationship("Srid", lazy="joined")

    tstype = Column(Integer, nullable=False)

    koordinater = relationship(
        "Koordinat",
        secondary=tidsserie_koordinat,
        back_populates="tidsserier",
        order_by=Koordinat.t,
    )

    __mapper_args__ = {
        "polymorphic_identity": "tidsserie",
        "polymorphic_on": tstype,
    }

    @property
    def referenceramme(self) -> str:
        return self.srid.kortnavn

    def __len__(self) -> int:
        return len(self.koordinater)

    @property
    def t(self) -> list[dt]:
        """
        Liste med t-komponenter fra tidsseriens koordinater givet som datetime objekt.
        """
        return [k.t for k in self.koordinater]

    @functools.cached_property
    def decimalår(self) -> list[float]:
        """
        Liste med t-komponenter fra tidsseriens koordinater givet i decimalår.
        """
        return [til_decimalår(k.t) for k in self.koordinater]


class GNSSTidsserie(Tidsserie):
    __mapper_args__ = {
        "polymorphic_identity": TidsserietypeID.gnss,
    }

    @property
    def tidsseriegruppe(self):
        (_, gruppenavn, _) = self.navn.split("_")
        return gruppenavn

    @functools.cached_property
    def x(self) -> List[float]:
        """
        Liste med x-komponenter fra tidsseriens koordinater.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        return [k.x for k in self.koordinater]

    @functools.cached_property
    def X(self) -> List[float]:
        """
        Liste med tidsseriens x-værdier normaliseret til tidsseriens første element.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        x0 = self.x[0]
        return [x - x0 for x in self.x]

    @functools.cached_property
    def y(self) -> List[float]:
        """
        Liste med y-komponenter fra tidsseriens koordinater.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        return [k.y for k in self.koordinater]

    @functools.cached_property
    def Y(self) -> List[float]:
        """
        Liste med tidsseriens y-værdier normaliseret til tidsseriens første element.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        y0 = self.y[0]
        return [y - y0 for y in self.y]

    @functools.cached_property
    def z(self) -> List[float]:
        """
        Liste med z-komponenter fra tidsseriens koordinater.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        return [k.z for k in self.koordinater]

    @functools.cached_property
    def Z(self) -> List[float]:
        """
        Liste med tidsseriens z-værdier normaliseret til tidsseriens første element.

        Koordinatkomponenten er i geocentrisk repræsentation.
        """
        z0 = self.z[0]
        return [z - z0 for z in self.z]

    @functools.cached_property
    def sx(self) -> List[float]:
        """
        Spredninger for tidsseriens x-komponenter.

        Spredning givet i milimeter.
        """
        return [k.sx for k in self.koordinater]

    @functools.cached_property
    def sy(self) -> List[float]:
        """
        Spredninger for tidsseriens y-komponenter.

        Spredning givet i milimeter.
        """
        return [k.sy for k in self.koordinater]

    @functools.cached_property
    def sz(self) -> List[float]:
        """
        Spredninger for tidsseriens z-komponenter.

        Spredning givet i milimeter.
        """
        return [k.sz for k in self.koordinater]

    @functools.cache
    def _neu(self):
        """
        Beregn topocentriske koordinatdifferencer for alle tre komponenter.

        Bruger fire.matematik.xyz2neu hvilket ikke nødvendigvis er den
        bedste løsning. Alternativt kan alle koordinater omregnes
        til længde, bredde og ellipsoidehøjde hvorefter
        storcirkelafstande mellem første og n'te punkte regnes med geod.
        Eller en version af xyz2neu der tager højde for ellipsoiden kan
        udvikles. Options, options, options...
        """
        # omtrentlig position, godt nok?
        lon, lat = self.punkt.geometri.koordinater
        return [xyz2neu(x, y, z, lat, lon) for x, y, z in zip(self.X, self.Y, self.Z)]

    @property
    def n(self):
        """
        Tidsseriens udvikling i nordlig retning, normaliseret til tidsseriens
        første element.
        """
        return [n for n, _, _ in self._neu()]

    @property
    def e(self):
        """
        Tidsseriens udvikling i østlig retning, normaliseret til tidsseriens
        første element.
        """
        return [e for _, e, _ in self._neu()]

    @property
    def u(self):
        """
        Tidsseriens udvikling i op-retningen, normaliseret til tidsseriens
        første element.
        """
        return [u for _, _, u in self._neu()]

    def _obs_liste(self, observationsklasse: Observation, attribut: str):
        observationer = []

        for k in self.koordinater:
            for obs in k.observationer:
                if isinstance(obs, observationsklasse):
                    observationer.append(obs.__getattribute__(attribut))
                    break
            else:
                observationer.append(None)

        return observationer

    @functools.cached_property
    def obslængde(self) -> List[float]:
        """
        Liste med observationslængder i timer for hver koordinat i tidsserien.

        Hvis den N'te koordinat ikke har observationslængde  registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ObservationsLængde, "varighed")

    @functools.cached_property
    def koordinatkovarians_xx(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens xx-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "xx")

    @functools.cached_property
    def koordinatkovarians_xy(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens xy-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "xy")

    @functools.cached_property
    def koordinatkovarians_xz(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens xz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "xz")

    @functools.cached_property
    def koordinatkovarians_yy(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens yy-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "yy")

    @functools.cached_property
    def koordinatkovarians_yz(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens yz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "yz")

    @functools.cached_property
    def koordinatkovarians_zz(self) -> List[float]:
        """
        Returner liste med koordinatkovariansmatrixens zz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(KoordinatKovarians, "zz")

    @functools.cached_property
    def koordinatkovarians(self) -> List[Tuple[float]]:
        """
        Returnerer liste med koordinatkovarians tuple for hver koordinat i tidsserien.

        Hver tuple er på formen (xx, xy, xz, yy, yz, zz).

        Hvis den N'te koordinat ikke har koordinatkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return list(
            zip(
                self.koordinatkovarians_xx,
                self.koordinatkovarians_xy,
                self.koordinatkovarians_xz,
                self.koordinatkovarians_yy,
                self.koordinatkovarians_yz,
                self.koordinatkovarians_zz,
            )
        )

    @functools.cached_property
    def residualkovarians_xx(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens xx-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "xx")

    @functools.cached_property
    def residualkovarians_xy(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens xy-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "xy")

    @functools.cached_property
    def residualkovarians_xz(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens xz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "xz")

    @functools.cached_property
    def residualkovarians_yy(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens yy-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "yy")

    @functools.cached_property
    def residualkovarians_yz(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens yz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "yz")

    @functools.cached_property
    def residualkovarians_zz(self) -> List[float]:
        """
        Returner liste med residualkovariansmatrixens zz-komponent for hver
        koordinat i tidsserien.

        Hvis den N'te koordinat ikke har residualkovariansmatrix registreret indsættes
        None i listen på plads N-1.
        """
        return self._obs_liste(ResidualKovarians, "zz")

    @staticmethod
    def binning(
        x: List[float], y: List[float], binsize: int = 14, **kwargs
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Kombiner data fra dage tættere på hinanden end binsize (i dage).

        x antages at være i decimalår og sorteret i stigende rækkefølge.
        Binning bruges som præprocessering til analyse med klassen PolynomieRegression1D.
        """

        if len(x) != len(y):
            raise ValueError("Inputdata skal have samme længde.")

        binsize_i_år = binsize / (365.25)
        x = np.array(x)
        y = np.array(y)
        vægt = np.ones(x.shape)
        xdiff = np.diff(x)

        while np.any(xdiff <= binsize_i_år):
            x_ny = []
            y_ny = []
            vægt_ny = []
            i = 0
            while i < len(x):
                bin_start = x[i]
                bin_slut = bin_start + binsize_i_år

                # Find alle datapunkter inden for [bin_start, bin_slut]
                bin = np.where(np.logical_and(bin_start <= x, x <= bin_slut))

                x_ny.append(sum(x[bin] * vægt[bin]) / sum(vægt[bin]))
                y_ny.append(sum(y[bin] * vægt[bin]) / sum(vægt[bin]))
                vægt_ny.append(sum(vægt[bin]))

                i = np.max(bin) + 1

            x, y, vægt = np.array(x_ny), np.array(y_ny), np.array(vægt_ny)
            xdiff = np.diff(x)

        return x, y

    def forbered_lineær_regression(self, x: list, y: list, **kwargs) -> None:
        """
        Opret "linreg" attribut af typen PolynomieRegression1D på tidsserien.

        Initialiserer en simpel PolynomieRegression i 1 dimension, dvs. med én
        forklarende variabel x, og én afhængig variabel y.

        Polynomiegraden sættes med kwarg'en "grad".
        Data kan reduceres med kwarg'en "binsize", se "GNSSTidsserie.binning(...)".
        """
        x_binned, y_binned = self.binning(x, y, **kwargs)

        self.linreg = PolynomieRegression1D(x_binned, y_binned, **kwargs)

    def beregn_lineær_regression(self) -> None:
        """
        Løs tidsseriens lineære regression.

        Forudsætter at denne er initialiseret med "forbered_lineær_regression(...)".
        """
        self.linreg.solve()


class TidsserieEnsemble:
    """
    Gruppér tidsserier og beregn tværgående statistik.

    Tidsserierne i ensemblet grupperes ud fra deres:
        - tidsserieklasse
        - tidsseriegruppe
        - referenceramme
    """

    def __init__(
        self,
        tidsserieklasse: Type,
        min_antal_punkter: int,
        tidsseriegruppe: str,
        referenceramme: str,
    ):
        self.tidsserieklasse = tidsserieklasse

        self.tidsserier = {}
        self.min_antal_punkter = min_antal_punkter
        self.tidsseriegruppe = tidsseriegruppe
        self.referenceramme = referenceramme

    def _valider_tidsserie(self, tidsserie: Tidsserie) -> None:
        """Valider en tidsserie inden indsættelse i ensemblet."""
        if (
            not isinstance(tidsserie, self.tidsserieklasse)
            or (len(tidsserie) < self.min_antal_punkter)
            or (tidsserie.tidsseriegruppe != self.tidsseriegruppe)
            or (tidsserie.referenceramme != self.referenceramme)
        ):
            raise ValueError(f"Tidsserie: {tidsserie.navn} kunne ikke valideres")

    def tilføj_tidsserie(self, tidsserie: Tidsserie) -> None:
        """Tilføj en tidsserie til ensemblet."""
        try:
            self._valider_tidsserie(tidsserie)
            print(f"Tilføjer tidsserie {tidsserie.navn}")
            self.tidsserier.update({tidsserie.navn: tidsserie})
        except ValueError as e:
            print(e)

    def beregn_samlet_varians(self) -> None:
        """
        Beregn den estimerede samlede varians af tidsserieensemblet.

        Den samlede varians beregnes som et vægtet gennemsnit af varianserne
        af de enkelte tidsserier som indgår i ensemblet, og opdaterer variansen
        i tidsserierne.

        Kræver at hver tidsserie har en linær regression "linreg"-attribut af typen
        PolynomieRegression1D, som er blevet løst, ved at få kørt sin "solve-metode."
        """
        if not self.tidsserier:
            raise ValueError(
                "Ingen tidsserier i ensemble. Kan ikke beregne samlet varians."
            )

        SSR_sum = 0
        dof_sum = 0

        for ts in self.tidsserier.values():
            SSR_sum += ts.linreg.SSR
            dof_sum += ts.linreg.dof

        self.var_samlet = SSR_sum / dof_sum

        # Opdater ensemblets tidsserier med den samlede varians.
        for ts in self.tidsserier.values():
            ts.linreg.var_samlet = self.var_samlet


class PolynomieRegression1D:
    """
    Foretag lineær regression over en tidsserie.
    """
    def __init__(
        self,
        x: list[float],
        y: list[float],
        y_vægte: float | list[float] = 1,
        grad: int = 1,
        **kwargs,
    ):
        self.x = np.array(x)
        self.y = np.array(y)
        self.grad = grad

        self._y_vægte = np.array(y_vægte)
        self._var0 = None
        self.var_samlet = None

    @functools.cached_property
    def _A(self) -> np.ndarray:
        """Returner designmatricen A"""
        return P.polyvander(self.x, self.grad)

    @functools.cached_property
    def _W(self) -> np.ndarray:
        """
        Returner diagonalen af vægtmatricen W

        Hvis vægtene er udefineret returneres enhedsmatricen. Pt. understøttes kun
        ukorrelerede observationer, dvs. at vægtmatricen er en diagonalmatrix.
        """
        return np.ones(self.N) * self._y_vægte

    @functools.cached_property
    def _invATA(self) -> np.ndarray:
        """
        Returner den inverse matrix af størrelsen (A^T * W * A)

        A er designmatricen for regressionen. W er vægtmatricen for observationerne.
        """
        return np.linalg.inv(self._A.T @ np.diag(self._W) @ self._A)

    def solve(self) -> None:
        """Løs hvad løses skal"""

        if self.dof <= 0:
            raise ValueError(
                "Antallet af punkter er mindre end eller lig antallet af parametre."
            )

        self.beta, [SSR, _, _, _] = P.polyfit(
            self.x, self.y, self.grad, full=True, w=self._W
        )

        if SSR.size == 0:
            raise ValueError(
                "Ligningssystemet har for lav rang. Kan forsøges fikset ved at normalisere data "
                "eller sætte polynomiegraden ned."
            )

        self.residualer = self.y - self.beregn_prædiktioner(self.x)
        self.SSR = np.dot(self._W, self.residualer**2)

        self._var0 = self.SSR / self.dof
        self.var_samlet = self._var0

    @property
    def R2(self) -> float:
        """
        Returner bestemmelseskoefficienten R².

        R² måler mængden af variation i data der forklares af modellen.
        """
        return 1 - (self.SSR / np.sum((self.y - self.y.mean()) ** 2))

    @property
    def ddof(self) -> int:
        """Returner "Delta Degrees of Freedom"."""
        return self.grad + 1

    @property
    def N(self) -> int:
        """Returner længden af tidsserien."""
        return len(self.x)

    @property
    def dof(self) -> int:
        """Returner antallet af frihedsgrader."""
        return self.N - self.ddof

    @property
    def var0(self) -> float:
        """Returner estimeret varians af residualer."""
        return self._var0

    @property
    def mex(self) -> float:
        """Returner middelepokedatoen."""
        return sum(self.x) / self.N

    @property
    def mey(self) -> float:
        """Returner regressionens værdi ved middelepokedatoen."""
        return P.polyval(self.mex, self.beta)

    def KovariansMatrix(self, er_samlet: bool = False) -> np.ndarray:
        """
        Returner kovariansmatrix for estimerede parametre β₀, β₁ ...

        Kovariansmatricen har følgende struktur:
        COV =  [[Var(β₀)    , Cov(β₀,β₁)],
                [Cov(β₁, β₀), Var(β₁)   ]]

        Kovariansmatricen beregnes som:
            COV = Var * (A^T * W * A)^(-1), hvor Var=SSR/dof
        Se fx. https://en.wikipedia.org/wiki/Weighted_least_squares#Parameter_errors_and_correlation
        """
        if er_samlet is False:
            var = self.var0
        elif er_samlet is True:
            var = self.var_samlet

        return var * self._invATA

    def VarBeta(self, er_samlet: bool = False) -> np.ndarray:
        """Returner den estimerede varians af de estimerede parametre βᵢ"""
        return np.diag(self.KovariansMatrix(er_samlet))

    def normaliser_data(
        self, a: float = -1, b: float = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Normaliserer tidsseriens x og y data til intervallet [a , b]."""

        def normaliser(data: np.ndarray, a: float, b: float):
            return a + (b - a) * (data - data.min()) / (data.max() - data.min())

        x_norm = normaliser(self.x, a, b)
        y_norm = normaliser(self.y, a, b)

        return x_norm, y_norm

    def beregn_konfidensinterval(
        self, alpha: float = 0.05, er_samlet: bool = False
    ) -> np.ndarray:
        """
        Beregn Konfidensintervaller på estimerede parametre βᵢ givet signifikansniveau alpha

        Konfidensintervaller beregnes ud fra formlen:
            ki = βᵢ ± krit * Var(βᵢ)
        hvor krit er en kritisk værdi bestemt ud fra "fordeling" med signifikansniveau alpha.

        Output er af typen np.ndarray(2,N), hvor N er antallet af parametre.
        """
        if er_samlet:
            fraktil = beregn_fraktil_for_normalfordeling(1 - alpha / 2)
        else:
            fraktil = beregn_fraktil_for_t_fordeling(1 - alpha / 2, self.dof)

        delta_ki = fraktil * np.sqrt(self.VarBeta(er_samlet))

        return self.beta + np.outer([-1, 1], delta_ki)

    def beregn_prædiktioner(self, x_præd: List[float]) -> np.ndarray:
        """Beregn regressionens værdi i punkterne x_præd."""
        return P.polyval(x_præd, self.beta)

    def beregn_konfidensbånd(
        self,
        x_præd: List[float],
        y_præd: List[float] = None,
        *,
        alpha: float = 0.05,
        er_samlet: bool = False,
    ) -> np.ndarray:
        """
        Beregn Konfidensbånd for regressionslinjen.

        Konfidensbåndet er givet ved:
            pi = prædiktion ± delta_pi

        Output er af typen np.ndarray(2,N), hvor N er antallet af punkter i x_præd.
        """

        if er_samlet:
            var = self.var_samlet
            fraktil = beregn_fraktil_for_normalfordeling(1 - alpha / 2)
        else:
            var = self.var0
            fraktil = beregn_fraktil_for_t_fordeling(1 - alpha / 2, self.dof)

        if y_præd is None:
            y_præd = self.beregn_prædiktioner(x_præd)

        A_præd = P.polyvander(x_præd, self.grad)
        delta_pi = fraktil * np.sqrt(var * np.diag(A_præd @ self._invATA @ A_præd.T))

        return y_præd + np.outer([-1, 1], delta_pi)

    def beregn_hypotesetest_hældning(
        self,
        reference_hældning: float = 0,
        alpha: float = 0.05,
        er_samlet: bool = False,
    ) -> "HypoteseTest":
        """
        Test om den estimerede hældning er signifikant forskellig fra en referenceværdi

        Returnerer objekt af typen HypoteseTest.
        """
        std_est = np.sqrt(self.VarBeta(er_samlet)[1])

        H0 = reference_hældning - self.beta[1]

        if er_samlet:
            return Ztest(std_est=std_est, H0=H0, alpha=alpha)

        return Ttest(std_est=std_est, dof=self.dof, H0=H0, alpha=alpha)


class HypoteseTest:
    """Foretag statistisk hypotesetest."""

    def __init__(
        self,
        std_est: float,
        kritiskværdi: float,
        H0: float = 0,
        alpha: float = 0.05,
    ):
        self.H0 = H0
        self.alpha = alpha
        self.std_est = std_est
        self.kritiskværdi = kritiskværdi

    @property
    def score(self) -> float:
        """Returner hypotesetestens score."""
        return abs(self.H0 / self.std_est)

    @property
    def H0accepteret(self) -> bool:
        """
        Evaluer hypotesetestens resultat.

        Hvis H0 accepteres, betyder det at der ikke kan påvises en signifikant forskel
        mellem den testede parameter og referencen.
        Omvendt, hvis H0 forkastes, betyder det at test-parameteren med signifikant
        sandsynlighed adskiller sig fra referencen.
        """
        return bool(self.score < self.kritiskværdi)


class Ztest(HypoteseTest):
    """Foretag statistisk Z-test"""

    def __init__(self, std_est: float, H0: float = 0, alpha: float = 0.05):

        kritiskværdi = beregn_fraktil_for_normalfordeling(1 - alpha / 2)
        super().__init__(std_est, kritiskværdi, H0, alpha)


class Ttest(HypoteseTest):
    """Foretag statistisk T-test"""

    def __init__(
        self,
        std_est: float,
        dof: int,
        H0: float = 0,
        alpha: float = 0.05,
    ):
        self.dof = dof
        kritiskværdi = beregn_fraktil_for_t_fordeling(1 - alpha / 2, dof)
        super().__init__(std_est, kritiskværdi, H0, alpha)


class HøjdeTidsserie(Tidsserie):
    __mapper_args__ = {
        "polymorphic_identity": TidsserietypeID.højde,
    }

    @functools.cached_property
    def kote(self) -> list[float]:
        """
        Liste med z-komponenter fra tidsseriens koordinater.

        Koterne er givet som ortometriske højder over tidsseriens jessenpunkt.

        For tidsserier uden tilknytning til et jessenpunkt (fx DVR90-tidsserier) svarer
        koternes referenceramme til tidsseriens referenceramme.
        """
        return [k.z for k in self.koordinater]

    @functools.cached_property
    def sz(self) -> list[float]:
        """
        Spredninger for tidsseriens z-komponenter.

        Spredning givet i milimeter.
        """
        return [k.sz for k in self.koordinater]

    def forbered_lineær_regression(self, x: list[float], y: list[float], **kwargs) -> None:
        """
        Opret "linreg" attribut af typen PolynomieRegression1D på tidsserien.

        Initialiserer en simpel PolynomieRegression i 1 dimension, dvs. med én
        forklarende variabel x, og én afhængig variabel y.
        """
        self.linreg = PolynomieRegression1D(x, y, **kwargs)

    def beregn_lineær_regression(self) -> None:
        """
        Løs tidsseriens lineære regression.

        Forudsætter at denne er initialiseret med "forbered_lineær_regression(...)".
        """
        self.linreg.solve()

    def signifikant_trend_test(self, alpha: float = 0.01) -> "HypoteseTest":
        """
        Test om punktets trend er signifikant forskellig fra 0.

        NB! Dette er en implementering af en gammel test. Førhen anvendtes den kritiske
        værdi TREND_SD_MULTIPLIER = 2.5 Nu anvendes T-test med signifikansniveau på 1 %,
        hvilket svarer til en kritisk værdi på 2.58 (for dof>>1).
        """

        return self.linreg.beregn_hypotesetest_hældning(
            reference_hældning=0, alpha=alpha
        )
