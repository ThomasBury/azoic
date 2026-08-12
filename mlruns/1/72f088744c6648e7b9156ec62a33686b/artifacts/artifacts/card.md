# RiskForge model card -- smoke

## Experiment
- name: `smoke`
- data: `C:\Users\B716CW\AppData\Local\Temp\pytest-of-B716CW\pytest-261\test_m6_acceptance_mlflow_run_0\portfolio.parquet`
- split: `random` (test_size=0.2, random_state=42)
- target: `claim_amount`  exposure: `exposure`
- rows: 2000  (train 1600 / test 400)
- features (4): `driver_age`, `vehicle_age`, `region`, `vehicle_brand`

### Model: `glm-tweedie` (glm)

- params: `{'family': 'tweedie', 'link': 'log', 'exposure_col': 'exposure', 'tweedie_power': 1.5}`
- gini (train): 0.2720
- gini (test):  0.1398
- O/P ratio (test):  1.0324
- deviance (test):  3659854.639959

#### Calibration table (test, first 12 rows)

| group | exposure | claim_amount | predicted_claim_amount | observed_pure_premium | predicted_pure_premium | o_p_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0000 | 29.4227 | 7044.4495 | 5409.5106 | 239.4220 | 183.8548 | 1.3022 |
| 1.0000 | 29.0304 | 15397.6553 | 8491.9485 | 530.3967 | 292.5187 | 1.8132 |
| 2.0000 | 28.1587 | 14625.8007 | 9894.1317 | 519.4054 | 351.3698 | 1.4782 |
| 3.0000 | 30.6480 | 7007.1355 | 13091.6305 | 228.6328 | 427.1611 | 0.5352 |
| 4.0000 | 30.2731 | 21261.3796 | 14892.5114 | 702.3203 | 491.9395 | 1.4277 |
| 5.0000 | 29.6018 | 19446.1502 | 16583.5717 | 656.9241 | 560.2213 | 1.1726 |
| 6.0000 | 30.7647 | 18698.2025 | 19143.0850 | 607.7804 | 622.2412 | 0.9768 |
| 7.0000 | 29.9458 | 29704.8211 | 21025.0103 | 991.9531 | 702.1023 | 1.4128 |
| 8.0000 | 29.8609 | 8624.8620 | 24638.3730 | 288.8349 | 825.1055 | 0.3501 |
| 9.0000 | 29.8342 | 28455.2455 | 31751.3429 | 953.7782 | 1064.2586 | 0.8962 |
