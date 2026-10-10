#include <M5Unified.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN 27
#define NUM_LEDS 25
#define GRID_SIZE 5

#define ACTIVE_BRIGHTNESS 28
#define SAFE_BRIGHTNESS 12

#define IDLE_STEP_MS 260

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

enum Status : char {
  STATUS_IDLE = 'I',
  STATUS_WORKING = 'W',
  STATUS_SUCCESS = 'S',
  STATUS_ERROR = 'E',
};

Status currentStatus = STATUS_IDLE;
uint8_t animFrame = 0;
uint32_t lastAnimMs = 0;
uint32_t lastIdleStepMs = 0;

int8_t dotX = 2;
int8_t dotY = 2;
int8_t targetX = 0;
int8_t targetY = 0;

const uint8_t PATTERN_CHECK[25] = {
  0, 0, 0, 0, 0,
  0, 0, 1, 0, 0,
  0, 1, 1, 1, 0,
  0, 0, 1, 0, 0,
  0, 1, 0, 0, 0,
};

const uint8_t PATTERN_X[25] = {
  1, 0, 0, 0, 1,
  0, 1, 0, 1, 0,
  0, 0, 1, 0, 0,
  0, 1, 0, 1, 0,
  1, 0, 0, 0, 1,
};

uint32_t colorRgb(uint8_t r, uint8_t g, uint8_t b) {
  return strip.Color(r, g, b);
}

uint8_t pixelIndex(uint8_t x, uint8_t y) {
  return y * GRID_SIZE + x;
}

void clearMatrix() {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, 0);
  }
  strip.show();
}

void drawPattern(const uint8_t pattern[25], uint32_t onColor) {
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, pattern[i] ? onColor : 0);
  }
  strip.show();
}

int8_t randomGridPos() {
  return (int8_t)random(0, GRID_SIZE);
}

void pickNewIdleTarget() {
  int8_t nextX;
  int8_t nextY;
  do {
    nextX = randomGridPos();
    nextY = randomGridPos();
  } while (nextX == dotX && nextY == dotY);
  targetX = nextX;
  targetY = nextY;
}

void resetIdleWander() {
  dotX = 2;
  dotY = 2;
  targetX = randomGridPos();
  targetY = randomGridPos();
  if (targetX == dotX && targetY == dotY) {
    pickNewIdleTarget();
  }
  lastIdleStepMs = millis();
}

void drawIdleWander() {
  strip.setBrightness(SAFE_BRIGHTNESS);
  uint32_t dimBlue = colorRgb(0, 6, 20);
  uint32_t brightBlue = colorRgb(0, 48, 210);

  for (uint8_t y = 0; y < GRID_SIZE; y++) {
    for (uint8_t x = 0; x < GRID_SIZE; x++) {
      uint8_t idx = pixelIndex(x, y);
      if ((int8_t)x == dotX && (int8_t)y == dotY) {
        strip.setPixelColor(idx, brightBlue);
      } else {
        strip.setPixelColor(idx, dimBlue);
      }
    }
  }
  strip.show();
}

void drawWorking(uint8_t frame) {
  strip.setBrightness(ACTIVE_BRIGHTNESS);
  clearMatrix();
  uint32_t orange = colorRgb(255, 90, 0);
  uint8_t pos = frame % NUM_LEDS;
  strip.setPixelColor(pos, orange);
  if (pos > 0) {
    strip.setPixelColor(pos - 1, colorRgb(80, 30, 0));
  } else {
    strip.setPixelColor(NUM_LEDS - 1, colorRgb(80, 30, 0));
  }
  strip.show();
}

void applyStatus(Status status) {
  currentStatus = status;
  animFrame = 0;
  lastAnimMs = millis();

  switch (status) {
    case STATUS_IDLE:
      resetIdleWander();
      drawIdleWander();
      break;
    case STATUS_WORKING:
      strip.setBrightness(ACTIVE_BRIGHTNESS);
      drawWorking(0);
      break;
    case STATUS_SUCCESS:
      strip.setBrightness(ACTIVE_BRIGHTNESS);
      drawPattern(PATTERN_CHECK, colorRgb(0, 220, 40));
      break;
    case STATUS_ERROR:
      strip.setBrightness(ACTIVE_BRIGHTNESS);
      drawPattern(PATTERN_X, colorRgb(220, 20, 20));
      break;
  }
}

void updateIdleAnimation() {
  uint32_t now = millis();
  if (now - lastIdleStepMs < IDLE_STEP_MS) {
    return;
  }
  lastIdleStepMs = now;

  if (dotX == targetX && dotY == targetY) {
    pickNewIdleTarget();
  }

  if (dotX < targetX) {
    dotX++;
  } else if (dotX > targetX) {
    dotX--;
  }

  if (dotY < targetY) {
    dotY++;
  } else if (dotY > targetY) {
    dotY--;
  }

  drawIdleWander();
}

void updateAnimation() {
  if (currentStatus == STATUS_IDLE) {
    updateIdleAnimation();
    return;
  }

  if (currentStatus == STATUS_WORKING) {
    uint32_t now = millis();
    if (now - lastAnimMs >= 90) {
      lastAnimMs = now;
      animFrame++;
      drawWorking(animFrame);
    }
  }
}

void handleSerial() {
  while (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == STATUS_IDLE || cmd == STATUS_WORKING || cmd == STATUS_SUCCESS || cmd == STATUS_ERROR) {
      applyStatus(static_cast<Status>(cmd));
    }
  }
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  randomSeed(esp_random());

  strip.begin();
  clearMatrix();
  applyStatus(STATUS_IDLE);
}

void loop() {
  M5.update();
  handleSerial();
  updateAnimation();

  if (M5.BtnA.wasPressed()) {
    Serial.println("BUTTON_PRESSED");
  }
}