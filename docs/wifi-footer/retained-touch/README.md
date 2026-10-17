# Retained-source touch regression

All 16 normal and 16 ASan/UBSan cases passed against the exact retained System Apps base `96742a20af660808cae6cd3a36eadd12a83a460f`, with only the footer controller replaced from merged repair `297c38619a867f6200cc2f605b6193e4394bdfa2`. The fixture and runner come from that repair revision. Production renderer, adapter and layout inputs remain from the retained source.

Cases cover scan start/cancel, repeated Next/Prev, inert footer gaps/content and Back at legacy 240×240 and native-height 240×240, 410×502 and 480×480. The receipts hash the exercised production inputs. Providers are synthetic; hardware remains untested.
