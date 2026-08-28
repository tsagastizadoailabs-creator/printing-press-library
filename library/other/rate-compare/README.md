# pp-rate-compare

**Mortgage rate scenario comparison CLI.**

Uses live FRED (Federal Reserve Bank of St. Louis) market rates + the Fannie Mae LLPA (Loan-Level Price Adjustment) matrix to show real payment impact across credit scores, loan products, and down payment scenarios.

No API key required.

## Install

```bash
go install github.com/tsagastizadoailabs-creator/printing-press-library/library/other/rate-compare/cmd/rate-compare-pp-cli@latest
```

## Usage

```bash
pp-rate-compare compare                          # 30yr vs 15yr vs 5yr ARM
pp-rate-compare scenario --fico 720 --ltv 80     # payment at specific FICO/LTV
pp-rate-compare fico-impact --loan 400000        # show rate across FICO tiers
pp-rate-compare down-payment --price 500000      # 3.5% vs 5% vs 10% vs 20%
```

## What makes it unique

Most mortgage calculators use a single fixed rate. This CLI layers the Fannie Mae LLPA matrix on top of live FRED benchmark rates — so the output reflects what a real borrower at a given FICO and LTV would actually pay, including lender markup.

## Built by

[Kapowsin Business Solutions](https://thekapowsincompany.com) — AI consulting for real estate professionals and mortgage lenders.
