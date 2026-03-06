"""Way2AGI Banner and description widget."""
from textual.widgets import Static

BANNER = r"""
 ╦ ╦┌─┐┬ ┬┌─┐╔═╗╔═╗╦
 ║║║├─┤└┬┘┌─┘╠═╣║ ╦║
 ╚╩╝┴ ┴ ┴ └─┘╩ ╩╚═╝╩
""".strip()

DESCRIPTION = """\
Dein persoenlicher KI-Agent der mit dir waechst.
Way2AGI verbindet freie & lokale Modelle mit echtem
Gedaechtnis und trainiert sich selbst — aus deiner Nutzung, auf deinem PC.

Anders als Chatbots hat Way2AGI einen kognitiven Kern:
Aufmerksamkeitssystem, Selbstbeobachtung und Verbesserung,
Bewusstseinsentwicklung — und Antriebe wie Neugier und
Kompetenzstreben die sein Handeln lenken — und ein
persistentes, aeusserst effizientes Gedaechtnis.

Der Orchestrator waehlt automatisch das beste Modell fuer jede Aufgabe:
schnelle Modelle fuer einfache Fragen, starke fuer komplexe Probleme,
mehrere gleichzeitig fuer kritische Entscheidungen.
586 Modelle, 9 Provider — ein Agent der sie alle intelligent kombiniert.

Kein Abo noetig. Keine Cloud. Deine Daten.
Freie Modelle · Lokales Memory · Selbsttraining · Kognitiver Kern · Multi-Modell Orchestrierung"""


class Way2AGIHeader(Static):
    """Banner + description displayed at top of dashboard."""

    def __init__(self) -> None:
        super().__init__(f"{BANNER}\n\n{DESCRIPTION}")
        self.add_class("way2agi-header")
