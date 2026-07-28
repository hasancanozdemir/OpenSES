The folders in this verification directory hold test files for various
different engineers' code changes.

## Deferred TODOs for Later Phases

These items are intentionally deferred while Phase 2 focuses on SI airflow
without fire-model refactoring.

1. Phase 3 fire-path absolute temperature cleanup:
	 - [source/INPUT.FOR](../source/INPUT.FOR): fire-source temperature storage
		 currently uses `ABTEMP` when moving to absolute temperature.
	 - [source/PINPNT.FOR](../source/PINPNT.FOR): fire radiation and glow terms
		 currently use `ABTEMP` in absolute-temperature expressions.
2. Phase 3 fire-path unit review:
	 - Confirm fire-path temperature assumptions for SI input mode.
	 - Replace any remaining hard-coded absolute-temperature offsets with
		 shared offsets where appropriate.
3. Phase 3 verification:
	 - Add focused fire-path SI/IP comparison cases (separate from Phase 2 P2
		 airflow cases).
