"""
Value Object pour les devises.
"""

from dataclasses import dataclass
from typing import Optional


# Devises supportees avec leurs symboles
CURRENCY_SYMBOLS = {
    "EUR": "\u20ac",  # Euro
    "USD": "$",
    "GBP": "\u00a3",  # Pound
    "CAD": "CA$",
    "AUD": "A$",
    "CHF": "CHF",
    "JPY": "\u00a5",  # Yen
    "CNY": "\u00a5",  # Yuan
    "INR": "\u20b9",  # Rupee
    "BRL": "R$",
    "MXN": "MX$",
    "PLN": "z\u0142",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
}

# Devises europeennes (pays de l'UE)
EU_CURRENCIES = frozenset({"EUR"})

# Devises courantes dans le dropshipping
DROPSHIP_CURRENCIES = frozenset({"EUR", "USD", "GBP", "CAD", "AUD"})


@dataclass(frozen=True, slots=True)
class Currency:
    """
    Devise monetaire.

    Represente une devise avec son code ISO 4217.

    Attributes:
        code: Code ISO 4217 de la devise (ex: "EUR", "USD").

    Example:
        >>> currency = Currency("EUR")
        >>> currency.symbol
        '\u20ac'
        >>> currency.format(99.99)
        '99.99 \u20ac'
    """

    code: str

    def __post_init__(self) -> None:
        """Normalise le code de devise."""
        if self.code:
            object.__setattr__(self, "code", self.code.upper().strip())

    @classmethod
    def from_string(cls, value: str) -> "Currency":
        """
        Cree une Currency depuis une chaine.

        Args:
            value: Code de devise ou symbole.

        Returns:
            Currency valide.

        Example:
            >>> Currency.from_string("eur")
            Currency(code='EUR')
        """
        if not value:
            return cls(code="")

        value = value.strip().upper()

        # Verifier si c'est un symbole
        for code, symbol in CURRENCY_SYMBOLS.items():
            if value == symbol or value == code:
                return cls(code=code)

        return cls(code=value)

    @classmethod
    def euro(cls) -> "Currency":
        """Factory pour Euro."""
        return cls(code="EUR")

    @classmethod
    def usd(cls) -> "Currency":
        """Factory pour Dollar US."""
        return cls(code="USD")

    @classmethod
    def unknown(cls) -> "Currency":
        """Factory pour devise inconnue."""
        return cls(code="")

    @property
    def symbol(self) -> str:
        """Retourne le symbole de la devise."""
        return CURRENCY_SYMBOLS.get(self.code, self.code)

    @property
    def is_known(self) -> bool:
        """Retourne True si la devise est connue."""
        return bool(self.code) and self.code in CURRENCY_SYMBOLS

    @property
    def is_euro(self) -> bool:
        """Retourne True si la devise est l'Euro."""
        return self.code == "EUR"

    @property
    def is_eu(self) -> bool:
        """Retourne True si c'est une devise de l'UE."""
        return self.code in EU_CURRENCIES

    @property
    def is_common_dropship(self) -> bool:
        """Retourne True si c'est une devise courante en dropshipping."""
        return self.code in DROPSHIP_CURRENCIES

    def format(self, amount: float, decimals: int = 2) -> str:
        """
        Formate un montant avec la devise.

        Args:
            amount: Montant a formater.
            decimals: Nombre de decimales.

        Returns:
            Montant formate (ex: "99.99 EUR").
        """
        formatted = f"{amount:,.{decimals}f}"
        if self.symbol:
            # Euro et GBP apres le montant
            if self.code in ("EUR", "GBP"):
                return f"{formatted} {self.symbol}"
            # Autres devises avant
            return f"{self.symbol}{formatted}"
        return formatted

    def __str__(self) -> str:
        """Retourne le code de la devise."""
        return self.code or "???"

    def __repr__(self) -> str:
        """Retourne la representation debug."""
        return f"Currency('{self.code}')"

    def __bool__(self) -> bool:
        """Retourne True si la devise est definie."""
        return bool(self.code)

    def __eq__(self, other: object) -> bool:
        """Compare deux devises."""
        if isinstance(other, Currency):
            return self.code == other.code
        if isinstance(other, str):
            return self.code == other.upper()
        return False

    def __hash__(self) -> int:
        """Hash de la devise."""
        return hash(self.code)
