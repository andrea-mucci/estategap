# Contract: Spider Registry Extensions

**Feature**: 025-eu-portals-enrichment  
**Interface type**: Internal Python module contract  
**Existing interface**: `services/spider-workers/estategap_spiders/spiders/__init__.py`

---

## New Spider Registrations

The following spider classes must be imported in `__init__.py` to trigger auto-registration:

```python
from estategap_spiders.spiders.it_immobiliare import ImmobiliareSpider  # noqa: F401
from estategap_spiders.spiders.it_idealista import IdealistaITSpider      # noqa: F401
from estategap_spiders.spiders.fr_seloger import SeLogerSpider            # noqa: F401
from estategap_spiders.spiders.fr_leboncoin import LeBonCoinSpider        # noqa: F401
from estategap_spiders.spiders.fr_bienici import BienIciSpider            # noqa: F401
from estategap_spiders.spiders.gb_rightmove import RightmoveSpider        # noqa: F401
from estategap_spiders.spiders.nl_funda import FundaSpider                # noqa: F401
```

After import, `get_spider("IT", "immobiliare")` returns `ImmobiliareSpider`, etc.

## Required Class Variables per Spider

```python
class {Portal}Spider(BaseSpider):
    COUNTRY: ClassVar[str] = "{CC}"          # ISO 3166-1 alpha-2 uppercase
    PORTAL: ClassVar[str] = "{portal_name}"  # lowercase, matches YAML filename prefix
```

## Registry Keys

| Key (country, portal) | Spider Class |
|-----------------------|-------------|
| `("IT", "immobiliare")` | `ImmobiliareSpider` |
| `("IT", "idealista")` | `IdealistaITSpider` |
| `("FR", "seloger")` | `SeLogerSpider` |
| `("FR", "leboncoin")` | `LeBonCoinSpider` |
| `("FR", "bienici")` | `BienIciSpider` |
| `("GB", "rightmove")` | `RightmoveSpider` |
| `("NL", "funda")` | `FundaSpider` |
