#include <M5Unified.h>
#include <Adafruit_NeoPixel.h>

#define LED_PIN 27
#define NUM_LEDS 25

#define ACTIVE_BRIGHTNESS 28
#define SAFE_BRIGHTNESS 12
#define ATTENTION_BRIGHTNESS 30

#define ATTENTION_INTERVAL_MS 15000
#define ATTENTION_PULSE_MS 700
#define SAFE_BREATHE_MS 80

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
uint32_t lastIdleAnimMs = 0;
uint32_t lastAttentionMs = 0;
uint32_t attentionStartMs = 0;
bool attentionPulseActive = false;
uint8_t safeBreatheLevel = 22;

const uint8_t ATTENTION_PIXELS[5] = {7, 11, 12, 13, 17};

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

uint8_t lerpU8(uint8_t a, uint8_t b, uint8_t t) {
  return a + ((int16_t)(b - a) * t) / 255;
}

bool isAttentionPixel(uint8_t index) {
  for (uint8_t i = 0; i < 5; i++) {
    if (ATTENTION_PIXELS[i] == index) {
      return true;
    }
  }
  return false;
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

void drawSafeIdle(uint8_t level) {
  strip.setBrightness(SAFE_BRIGHTNESS);
  uint32_t dimBlue = colorRgb(0, 8, level);
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, dimBlue);
  }
  strip.show();
}

void drawAttentionPulse(uint8_t strength) {
  strip.setBrightness(lerpU8(SAFE_BRIGHTNESS, ATTENTION_BRIGHTNESS, strength));
  uint32_t dimBlue = colorRgb(0, 10, 28);

  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    if (isAttentionPixel(i)) {
      strip.setPixelColor(i, colorRgb(
        (40 * strength) / 255,
        (80 * strength) / 255,
        lerpU8(60, 255, strength)
      ));
    } else {
      strip.setPixelColor(i, dimBlue);
    }
  }
  strip.show();
}

void resetIdleAttention() {
  attentionPulseActive = false;
  lastAttentionMs = millis();
  lastIdleAnimMs = millis();
  safeBreatheLevel = 22;
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
      resetIdleAttention();
      drawSafeIdle(safeBreatheLevel);
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

  if (!attentionPulseActive && now - lastAttentionMs >= ATTENTION_INTERVAL_MS) {
    attentionPulseActive = true;
    attentionStartMs = now;
  }

  if (attentionPulseActive) {
    uint32_t elapsed = now - attentionStartMs;
    if (elapsed >= ATTENTION_PULSE_MS) {
      attentionPulseActive = false;
      lastAttentionMs = now;
      drawSafeIdle(safeBreatheLevel);
      return;
    }

    uint8_t strength;
    uint32_t half = ATTENTION_PULSE_MS / 2;
    if (elapsed < half) {
      strength = (uint8_t)((elapsed * 255) / half);
    } else {
      strength = (uint8_t)(((ATTENTION_PULSE_MS - elapsed) * 255) / half);
    }
    drawAttentionPulse(strength);
    return;
  }

  if (now - lastIdleAnimMs >= SAFE_BREATHE_MS) {
    lastIdleAnimMs = now;
    static int8_t breatheDir = 1;
    safeBreatheLevel += breatheDir;
    if (safeBreatheLevel >= 30) {
      safeBreatheLevel = 30;
      breatheDir = -1;
    } else if (safeBreatheLevel <= 18) {
      safeBreatheLevel = 18;
      breatheDir = 1;
    }
    drawSafeIdle(safeBreatheLevel);
  }
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