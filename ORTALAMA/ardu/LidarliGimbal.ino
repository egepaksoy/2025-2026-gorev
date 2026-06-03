// Gimbal kontrol kodu
#include <Servo.h>

Servo servoX;
Servo servoY;

int servoY_Min = 10;
int servoY_Max = 115;

int servoX_Mid = 95;

int servoX_Val = servoX_Mid;
int servoY_Val = 0;
int servoY_Write_Val = servoY_Min;

void setup() {
  Serial.begin(9600);
  servoY.attach(11);
  servoX.attach(10);

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

    /*
    Serial.print("Y: ");
    Serial.println(girisAciY);
    
    Serial.print("X: ");
    Serial.println(girisAciX);
    */

    // 1. Servo Kontrol ve Yazdırma
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

    // Akım koruması için kısa bekleme (Bağlantı kopmasını önler)
    delay(15); 

    // 2. Servo Kontrol ve Yazdırma
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
    else if (servoY_Val + girisAciY > 180) {
      servoY_Val = 90;
      servoY_Write_Val = map(servoY_Val, 0, 90, servoY_Min, servoY_Max);
      servoY.write(servoY_Write_Val);
    }
    
    Serial.print(servoX_Val - servoX_Mid);
    Serial.print("|");
    Serial.println(servoY_Val);
  }
}