# pp-zillow

**Zillow Zestimate + deal intelligence CLI.**

Restores access to Zillow's AVM (Automated Valuation Model) data after Zillow shut down their public Zestimate API in 2021. Uses Chrome TLS fingerprinting to fetch Zestimate, rentZestimate, and taxAssessedValue from the embedded page state — no API key required.

Built for real estate investors and agents who need fast, scriptable access to Zillow valuation data.

## Install

```bash
go install github.com/tsagastizadoailabs-creator/printing-press-library/library/other/zillow/cmd/zillow-pp-cli@latest
```

## Usage

```bash
pp-zillow search <city>              # search listings by city
pp-zillow zestimate <address>        # get Zestimate for a specific address
pp-zillow deals <city>               # find properties where Zestimate > list price
pp-zillow compare <url1> <url2>      # compare two listings
```

## What it returns

- Zestimate (AVM value)
- rentZestimate (rental AVM)
- Tax assessed value
- Days on Zillow, beds/baths, sqft
- Zestimate gap % (vs. list price — positive = Zillow thinks it's underpriced)

## Built by

[Kapowsin Business Solutions](https://thekapowsincompany.com) — AI consulting for real estate professionals.
