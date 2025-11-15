#!/usr/bin/env python3
# OPTIONAL analog (pygame required). Not needed for main simulator.
import time, random, json, os, datetime
try:
    import pygame
    from pygame.locals import *
except Exception:
    print("Requires pygame. Install: pip install pygame")
    raise

def now_ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def run():
    pygame.init(); pygame.joystick.init()
    if pygame.joystick.get_count()==0:
        print("No joystick detected."); return
    js = pygame.joystick.Joystick(0); js.init()
    screen = pygame.display.set_mode((800, 400))
    clock = pygame.time.Clock()
    target_x = 400; x = 400; drift = 0.0
    start = time.time(); duration = 90
    errs = []; running = True
    while running and time.time()-start < duration:
        for ev in pygame.event.get():
            if ev.type == QUIT: running = False
        axis = js.get_axis(0)
        drift += random.uniform(-0.8,0.8)
        x += axis*8 + drift*0.2
        x = max(0, min(800, x))
        err = abs(x - target_x)/400.0; errs.append(err)
        screen.fill((255,255,255))
        pygame.draw.line(screen, (0,0,0), (400,0), (400,400), 2)
        pygame.draw.circle(screen, (0,0,255), (int(x), 200), 10)
        pygame.display.flip(); clock.tick(60)
    acc = max(0.0, 100.0*(1.0 - (sum(errs)/len(errs) if errs else 1.0)))
    os.makedirs("sessions", exist_ok=True)
    ts = now_ts()
    with open(f"sessions/joystick_{ts}.json","w") as f:
        json.dump({"timestamp": ts, "analog_tracking_score": acc}, f, indent=2)
    print(f"Analog tracking score: {acc:.1f} — saved to sessions/")

if __name__ == "__main__":
    run()
