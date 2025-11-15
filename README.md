# RSAF COMPASS-Style Pilot (Fighter) Mock Suite — v2

**Included**
- 8 modules: Control, Slalom, Memory, Task Manager, Orientation, Mathematics, Technical (fighter-oriented), Verbal
- 3 levels (Basic / Standard / Hard)
- Real-session pacing (~80–90 mins) with short breaks
- Weighted scoring + JSON/CSV logs
- Percentile tracker (compares with last 10 runs)
- Coaching notes (auto-picked for your 2 weakest modules)
- One-page PDF summary after each run
- Optional joystick analog script (requires `pygame`) included

**Run**
```bash
python3 compass_simulator.py
```
Choose a mode:
- **Full session** – runs the full ~90 min flow with warm-ups and breaks.
- **Practice** – opens a menu so you can launch any module individually. Each practice run saves its own JSON file in `sessions/` (similar to the optional joystick tracker).

You can also skip the prompt via `python3 compass_simulator.py --mode practice` or `--mode session`.

**Optional analog**
```bash
pip install pygame
python3 optional_joystick_pygame.py
```
