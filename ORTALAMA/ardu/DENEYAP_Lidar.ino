// Deneyap A1 v2 (ESP32) Uyumlu Bağıl Gimbal Kontrol Kodu
#include <ESP32Servo.h> // ESP32 için özel servo kütüphanesi

Servo servoX;
Servo servoY;

// Deneyap A1 v2 üzerindeki PWM destekli pinler seçildi
// Fiziksel bağlantına göre D10 ve D11 yerine kart üzerindeki diğer pinleri de seçebilirsin.
const int servoXPin = D10;
const int servoYPin = D11;

int servoY_Min = 10;
int servoY_Max = 115;

int servoX_Mid = 95;

int servoX_Val = servoX_Mid;
int servoY_Val = 0;
int servoY_Write_Val = servoY_Min;

void setup() {
  Serial.begin(9600);
  
  // ESP32Servo kütüphanesinde donanımsal zamanlama (timer) çakışmalarını önler
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  
  // Standart servoların 50Hz çalışma frekansı set edilir
  servoX.setPeriodHertz(50);
  servoY.setPeriodHertz(50);

  // Servoları Deneyap pinlerine bağla
  servoX.attach(servoXPin);
  servoY.attach(servoYPin);

  // Başlangıç konumuna gönder
  servoX.write(servoX_Val);
  servoY.write(servoY_Write_Val);
}

void loop() {
  if (Serial.available() > 0) {
    // Veriyi parçala
    String veriX = Serial.readStringUntil('|');
    String veriY = Serial.readStringUntil('\n');

    int girisAciX = veriX.toInt(); 
    int girisAciY = veriY.toInt();

    // 1. Servo (X Ekseni) Kontrolü
    if (servoX_Val + girisAciX >= 0 && servoX_Val + girisAciX <= 180) {
      servoX_Val += girisAciX;
      servoX.write(servoX_Val);
    }
    else if (servoX_Val + girisAciX < 0) {
      servoX_Val = 0;
      servoX.write(servoX_Val);
    }
    else if (servoX_Val + girisAciX > 180) {
      servoX_Val = 180;
      servoX.write(servoX_Val);
    }

    // Akım koruması ve ESP32 kararlılığı için kısa bekleme
    delay(15); 

    // 2. Servo (Y Ekseni) Kontrolü
    if (servoY_Val + girisAciY >= 0 && servoY_Val + girisAciY <= 90) {
      servoY_Val += girisAciY;
      servoY_Write_Val = map(servoY_Val, 0, 90, servoY_Min, servoY_Max);
      servoY.write(servoY_Write_Val);
    }
    else if (servoY_Val + girisAciY < 0) {
      servoY_Val = 0;
      servoY_Write_Val = map(servoY_Val, 0, 90, servoY_Min, servoY_Max);
      servoY.write(servoY_Write_Val);
    }
    // Orijinal koddaki 180 sınır kontrolü mantığı korundu (Y ekseni üst sınırı)
    else if (servoY_Val + girisAciY > 180) { 
      servoY_Val = 90;
      servoY_Write_Val = map(servoY_Val, 0, 90, servoY_Min, servoY_Max);
      servoY.write(servoY_Write_Val);
    }
    
    // Geri bildirim verisini seri porttan gönder
    Serial.print(servoX_Val - servoX_Mid);
    Serial.print("|");
    Serial.println(servoY_Val);
  }
}