from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    name_ar: str


# Candidate universe of large/mid-cap US-listed companies whose primary business is
# NOT conventional banking, insurance, alcohol, gambling, tobacco, pork, adult
# entertainment or defense manufacturing. Inclusion here only means a stock is a
# *candidate* worth scanning - actual Sharia compliance is always (re)computed live
# from current financial ratios by the screening engine, never assumed from this list.
CURATED_UNIVERSE: tuple[UniverseEntry, ...] = (
    UniverseEntry("AAPL", "أبل"),
    UniverseEntry("MSFT", "مايكروسوفت"),
    UniverseEntry("NVDA", "إنفيديا"),
    UniverseEntry("GOOGL", "ألفابت / جوجل"),
    UniverseEntry("AMZN", "أمازون"),
    UniverseEntry("META", "ميتا"),
    UniverseEntry("TSLA", "تسلا"),
    UniverseEntry("AVGO", "برودكوم"),
    UniverseEntry("ORCL", "أوراكل"),
    UniverseEntry("ADBE", "أدوبي"),
    UniverseEntry("CRM", "سيلزفورس"),
    UniverseEntry("AMD", "أيه إم دي"),
    UniverseEntry("QCOM", "كوالكوم"),
    UniverseEntry("INTC", "إنتل"),
    UniverseEntry("CSCO", "سيسكو"),
    UniverseEntry("IBM", "آي بي إم"),
    UniverseEntry("NOW", "سيرفس ناو"),
    UniverseEntry("INTU", "إنتويت"),
    UniverseEntry("TXN", "تكساس إنسترومنتس"),
    UniverseEntry("AMAT", "أبلايد ماتيريالز"),
    UniverseEntry("MU", "مايكرون"),
    UniverseEntry("ADI", "أناالوغ ديفايسز"),
    UniverseEntry("LRCX", "لام ريسيرش"),
    UniverseEntry("SNPS", "سينوبسيس"),
    UniverseEntry("CDNS", "كادنس"),
    UniverseEntry("PANW", "بالو ألتو نتوركس"),
    UniverseEntry("CRWD", "كراودسترايك"),
    UniverseEntry("SHOP", "شوبيفاي"),
    UniverseEntry("UBER", "أوبر"),
    UniverseEntry("ABNB", "إير بي إن بي"),
    UniverseEntry("NFLX", "نتفليكس"),
    UniverseEntry("PYPL", "باي بال"),
    UniverseEntry("SQ", "بلوك"),
    UniverseEntry("JNJ", "جونسون آند جونسون"),
    UniverseEntry("PFE", "فايزر"),
    UniverseEntry("ABBV", "أبفي"),
    UniverseEntry("MRK", "ميرك"),
    UniverseEntry("LLY", "إيلي ليلي"),
    UniverseEntry("UNH", "يونايتد هيلث"),
    UniverseEntry("TMO", "ثيرمو فيشر"),
    UniverseEntry("ABT", "أبوت"),
    UniverseEntry("DHR", "دانهر"),
    UniverseEntry("ISRG", "إنتويتيف سيرجيكال"),
    UniverseEntry("VRTX", "فيرتكس فارماسيوتيكالز"),
    UniverseEntry("REGN", "ريجينيرون"),
    UniverseEntry("PG", "بروكتر آند غامبل"),
    UniverseEntry("COST", "كوستكو"),
    UniverseEntry("WMT", "وول مارت"),
    UniverseEntry("KO", "كوكا كولا"),
    UniverseEntry("PEP", "بيبسيكو"),
    UniverseEntry("MDLZ", "مونديليز"),
    UniverseEntry("CL", "كولجيت بالموليف"),
    UniverseEntry("EL", "إستي لودر"),
    UniverseEntry("NKE", "نايكي"),
    UniverseEntry("SBUX", "ستاربكس"),
    UniverseEntry("MCD", "ماكدونالدز"),
    UniverseEntry("HD", "هوم ديبوت"),
    UniverseEntry("LOW", "لوز"),
    UniverseEntry("TJX", "تي جيه إكس"),
    UniverseEntry("XOM", "إكسون موبيل"),
    UniverseEntry("CVX", "شيفرون"),
    UniverseEntry("COP", "كونوكو فيليبس"),
    UniverseEntry("SLB", "شلمبرجير"),
    UniverseEntry("EOG", "إي أو جي ريسورسز"),
    UniverseEntry("LIN", "ليندي"),
    UniverseEntry("APD", "إير برودكتس"),
    UniverseEntry("SHW", "شيروين ويليامز"),
    UniverseEntry("ECL", "إيكولاب"),
    UniverseEntry("CAT", "كاتربيلر"),
    UniverseEntry("DE", "دير آند كومباني"),
    UniverseEntry("HON", "هانيويل"),
    UniverseEntry("UPS", "يو بي إس"),
    UniverseEntry("UNP", "يونيون باسيفيك"),
    UniverseEntry("EMR", "إيمرسون إلكتريك"),
    UniverseEntry("ETN", "إيتون"),
    UniverseEntry("ITW", "إيليونوي تول ووركس"),
    UniverseEntry("NEE", "نيكستيرا إنرجي"),
    UniverseEntry("DUK", "ديوك إنرجي"),
    UniverseEntry("SO", "ساذرن كومباني"),
    UniverseEntry("AEP", "أمريكان إلكتريك باور"),
    UniverseEntry("T", "إيه تي آند تي"),
    UniverseEntry("VZ", "فيرايزون"),
    UniverseEntry("TMUS", "تي موبايل"),
    UniverseEntry("CMCSA", "كومكاست"),
    UniverseEntry("AMT", "أمريكان تاور"),
    UniverseEntry("PLD", "بروليجيس"),
    UniverseEntry("EQIX", "إكوينيكس"),
)


def get_universe_tickers() -> list[str]:
    return [entry.ticker for entry in CURATED_UNIVERSE]


def get_arabic_name(ticker: str) -> str | None:
    for entry in CURATED_UNIVERSE:
        if entry.ticker == ticker:
            return entry.name_ar
    return None
