// Deneyap A1 v2 (ESP32) uyumlu Gimbal kontrol kodu
#include <ESP32Servo.h> // ESP32 için özel servo kütüphanesi

Servo servo1;
Servo servo2;

// Deneyap A1 v2 üzerindeki PWM destekli pinler seçildi (Örn: D8 ve D9)
// İsterseniz kart üzerindeki diğer PWM pinlerini de (D0, D1 vb.) kullanabilirsiniz.
const int servo1Pin = D9; 
const int servo2Pin = D8;

void setup() {
  Serial.begin(9600);
  
  // ESP32Servo kütüphanesinde zamanlama (timer) çakışmalarını önlemek için atanır
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  
  // Standart servolar genellikle 50Hz frekansta çalışır
  servo1.setPeriodHertz(50);
  servo2.setPeriodHertz(50);

  // Servoları pinlere bağla
  servo1.attach(servo1Pin);
  servo2.attach(servo2Pin);
}

void loop() {
  if (Serial.available() > 0) {
    // Veriyi parçala
    // Not: Gelen verinin "veri2|veri1\n" formatında olduğundan emin olun.
    String veri2 = Serial.readStringUntil('|');
    String veri1 = Serial.readStringUntil('\n');

    int girisAci1 = veri1.toInt(); 
    int girisAci2 = veri2.toInt();

    // 1. SERVO ORANLAMA (D9 Pini - servo1)
    // 0 -> 2 derece | 180 -> 165 derece
    int cikisAci1 = map(girisAci1, 0, 180, 2, 165);

    // 2. SERVO ORANLAMA (D8 Pini - servo2)
    // 0 -> 87 derece | 90 -> 167 derece
    int cikisAci2 = map(girisAci2, 0, 90, 87, 167);

    // 1. Servo Kontrol
    if (girisAci1 >= 0 && girisAci1 <= 180) {
      servo1.write(cikisAci1);
    }

    // Akım koruması ve kararlılık için kısa bekleme (Bağlantı kopmasını önler)
    delay(50); 

    // 2. Servo Kontrol
    if (girisAci2 >= 0 && girisAci2 <= 90) {
      servo2.write(cikisAci2);
    }
    
    delay(50);
  }
}