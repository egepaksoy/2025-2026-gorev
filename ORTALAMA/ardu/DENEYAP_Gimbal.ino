#include <ESP32Servo.h>

Servo servo1;
Servo servo2;

const int servoPin1 = D0; // D0 pini
const int servoPin2 = D1; // D0 pini


void setup() {
  Serial.begin(9600);

  servo1.setPeriodHertz(50); // Standart servo frekansı
  servo1.attach(servoPin1, 500, 2400); // Pulse aralığını belirleyerek kararlılığı artırın

  servo2.setPeriodHertz(50); // Standart servo frekansı
  servo2.attach(servoPin2, 500, 2400); // Pulse aralığını belirleyerek kararlılığı artırın  
}

void loop() {
  if (Serial.available() > 0) {
    // Veriyi parçala
    String veri2 = Serial.readStringUntil('|');
    String veri1 = Serial.readStringUntil('\n');

    int girisAci1 = veri1.toInt(); 
    int girisAci2 = veri2.toInt();

    // 1. SERVO ORANLAMA (8. PIN)
    // 0 -> 2 derece | 180 -> 165 derece
    int cikisAci1 = map(girisAci1, 0, 180, 2, 165);

    // 2. SERVO ORANLAMA (9. PIN)
    // 0 -> 87 derece | 90 -> 167 derece
    int cikisAci2 = map(girisAci2, 0, 90, 87, 167);

    // 1. Servo Kontrol ve Yazdırma
    if (girisAci1 >= 0 && girisAci1 <= 180) {
      servo1.write(cikisAci1);
    }

    // Akım koruması için kısa bekleme (Bağlantı kopmasını önler)
    delay(150); 

    // 2. Servo Kontrol ve Yazdırma
    if (girisAci2 >= 0 && girisAci2 <= 90) {
      servo2.write(cikisAci2);
    }
    Serial.print(cikisAci1);
    Serial.print(" - ");
    Serial.println(cikisAci2);
  }
}