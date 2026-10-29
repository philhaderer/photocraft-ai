# MOSS Text to image ohne DMD2: CFG und Steps (Blindtest 29.10.)

Anlass: Der User fand MOSS Text to image mit den alten Startwerten künstlich; gut war am zweiten Rechner DMD2 aus, SLG aus, 25 Steps, ohne LLM (PLAN 10c). Offen blieb, welcher CFG-Wert ohne DMD2 gilt: der Workflow sah 2.5 vor, sein Test lief wohl mit 1.5 (der LoRA-Haken stellte die Felder damals nicht um, Fehler inzwischen behoben). Danach las der User die MOSS-Image-Anleitung (USERGUIDE.md: gilt für das Base-Modell, empfiehlt CFG 3 bis 6, mindestens 50 Steps, Euler, Shift 5; „SLG aus sieht sehr realistisch aus, Details können zerfallen“) und wollte zusätzlich CFG 3.0 bei 35 Steps sehen.

Aufbau (`tests/live_moss_cfg.py`): MOSS SFT int8, UltraReal-LoRA an, DMD2 aus, SLG aus, kein LLM, er_sde / simple, 1280 x 1280. 10 realistische Prompts aus `docs/tests/testprompts.md` (73, 74, 79, 81 Gesichter; 115, 116 Materialien; 143, 144 Kamera; 166, 168 Produktfoto), je 2 Seeds (101, 202) = 20 Paare je Runde. Bewertung blind im Paar (links / rechts zufällig, Variante verborgen). Rohdaten: `data/moss-cfg-test/<Zeit>/` (nicht im Repo).

## Runde 1: CFG 1.5 gegen 2.5, beide 25 Steps (ca. 22 s je Bild)

| CFG 1.5 besser | CFG 2.5 besser | gleich gut | beide schlecht |
|---|---|---|---|
| 6 | 2 | 12 | 0 |

1.5 klar bei 81 und 116 (beide Seeds), 2.5 je einmal bei 73 und 144.

## Runde 2: CFG 1.5 / 25 Steps gegen CFG 3.0 / 35 Steps (ca. 30 s je Bild)

| CFG 1.5, 25 Steps besser | CFG 3.0, 35 Steps besser | gleich gut | beide schlecht |
|---|---|---|---|
| 5 | 8 | 7 | 0 |

3.0/35 klar bei 74 und 144, 1.5/25 klar bei 81 (beide Seeds); die Produktfotos 166 und 168 gleich.

## Entscheidung des Users

**CFG 3.0, 35 Steps** (29.10.): `pc_no_lora` von `moss-image-t2i.json`, Steps-Tooltip „Turn up the steps to 35 for best results.“ Einschränkung: der Vorsprung ist klein, und in Runde 2 änderten sich CFG und Steps zugleich (welcher der beiden den Unterschied macht, ist offen). Nicht getestet: Euler, Shift 5, 50 Steps.
