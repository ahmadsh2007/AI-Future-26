# Fee cases report

Source: `eval/fee_cases.json` (built by `eval/build_fee_cases.py`, checked by `eval/check_fee_cases.py`).

- items: 57, cases: 73
- multi-person / multi-service items: 13
- durations/ages in words or dialect: 27
- missing-detail items (all candidates, total null): 7
- cases with an added total: 10
- check result: PASS (0 errors, 12 warnings)

Look-alike warnings are intended: services with one fee (damaged, ID renewal) use the fee of a
sibling service (e.g. 125 of passport_lost for passport_damaged) as the wrong-file amount.

| service | cases |
|---|---|
| family_book_damaged | 2 |
| family_book_first_issue | 4 |
| family_book_lost | 5 |
| family_book_renewal | 4 |
| id_card_damaged | 3 |
| id_card_first_issue | 6 |
| id_card_lost | 9 |
| id_card_renewal | 2 |
| passport_damaged | 2 |
| passport_first_issue | 9 |
| passport_lost | 6 |
| passport_renewal | 21 |

## Warnings

- fee-24 case 0 (passport_damaged): must_not amount 125 comes from a look-alike service
- fee-24 case 0 (passport_damaged): must_not amount 20 comes from a look-alike service
- fee-34 case 0 (family_book_damaged): must_not amount 5 comes from a look-alike service
- fee-35 case 0 (family_book_damaged): must_not amount 5 comes from a look-alike service
- fee-39 case 0 (id_card_renewal): must_not amount 3 comes from a look-alike service
- fee-39 case 0 (id_card_renewal): must_not amount 5 comes from a look-alike service
- fee-45 case 0 (id_card_damaged): must_not amount 5 comes from a look-alike service
- fee-45 case 0 (id_card_damaged): must_not amount 2 comes from a look-alike service
- fee-49 case 2 (id_card_damaged): must_not amount 5 comes from a look-alike service
- fee-54 case 0 (passport_damaged): must_not amount 125 comes from a look-alike service
- fee-54 case 1 (id_card_damaged): must_not amount 5 comes from a look-alike service
- fee-57 case 0 (id_card_renewal): must_not amount 3 comes from a look-alike service
