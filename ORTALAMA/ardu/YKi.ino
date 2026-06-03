// Pin Tanımlamaları
const int JOY_X_PIN = A0;      // Joystick X ekseni
const int JOY_Y_PIN = A1;      // Joystick Y ekseni
const int JOY_SW_PIN = 2;      // Joystick üzerindeki buton
const int BUTTON_1_PIN = 3;    // Harici Buton 1
const int BUTTON_2_PIN = 4;    // Harici Buton 2

void setup() {
  // Seri haberleşmeyi başlat
  Serial.begin(115200);

  // Pin modlarını ayarla
  // INPUT_PULLUP kullanıldığı için butonun diğer ucu GND'ye bağlanmalıdır.
  // Butona basıldığında okunan değer 0 (LOW) olur.
  pinMode(JOY_SW_PIN, INPUT_PULLUP);
  pinMode(BUTTON_1_PIN, INPUT_PULLUP);
  pinMode(BUTTON_2_PIN, INPUT_PULLUP);
}

void loop() {
  // Analog verileri oku (0 - 1023 arası)
  int xValue = 1023 - analogRead(JOY_X_PIN);
  int yValue = 1023 - analogRead(JOY_Y_PIN);

  // Buton durumlarını oku (0: Basılı, 1: Boşta)
  int joySw = digitalRead(JOY_SW_PIN);
  int btn1 = digitalRead(BUTTON_1_PIN);
  int btn2 = digitalRead(BUTTON_2_PIN);

  // Verileri Seri Port Ekranına Yazdır
  Serial.print("X:");
  Serial.print(xValue);
  
  Serial.print(" | Y:");
  Serial.print(yValue);
  
  Serial.print(" | Joy_SW:");
  Serial.print(joySw == LOW ? "1" : "0");
  
  Serial.print(" | Buton_1:");
  Serial.print(btn1 == LOW ? "1" : "0");
  
  Serial.print(" | Buton_2:");
  Serial.println(btn2 == LOW ? "1" : "0");

  // Okunabilirliği artırmak için kısa bir gecikme
  delay(100);
}