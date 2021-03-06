// this example is public domain. enjoy!
// https://learn.adafruit.com/thermocouple/

#include "max6675.h"
#include <Wire.h>
#include <Adafruit_MCP4725.h>
#include <PID_v2.h>

Adafruit_MCP4725 dac;
// For MCP4725A0 the address is 0x60 or 0x61

int addrs[2] = {0x60, 0x61};
int sensorValue = 0;

int mainDO = 2;
int mainCS = 3;
int mainCLK = 4;

int halcDO = 8;
int halcCS = 9;
int halcCLK = 10;

double main_temp = 0;
double halc_temp = 0;
float ar_flow = 0;
float h2_flow = 0;

double main_temp_setpoint = 0;
double halc_temp_setpoint =   0;
float ar_flow_setpoint = 0;
float h2_flow_setpoint = 0;

double main_gains[] = {50, 100, 50};
double halc_gains[] = {50, 10, 10};

double main_temp_output = 0;
double halc_temp_output = 0;

const int main_pin =  5;
int main_state = HIGH;
const int halc_pin =  6;
int halc_state = HIGH;

const int main_pwmPeriod = 2000;
const int halc_pwmPeriod = 2000;

float main_pwmDuty = 0.5;
float halc_pwmDuty = 0.5;

unsigned long main_t0 = 0;
unsigned long halc_t0 = 0;

char serbuff[40];
int ibuff = 0;

bool internal_PID_control = false;

//Define temperature PID control
PID main_temp_control(&main_temp, &main_temp_output, &main_temp_setpoint, main_gains[0], main_gains[1], main_gains[2], DIRECT);
PID halc_temp_control(&halc_temp, &halc_temp_output, &halc_temp_setpoint, halc_gains[0], halc_gains[1], halc_gains[2], DIRECT);


//Define read devices
MAX6675 main_read(mainCLK, mainCS, mainDO);
MAX6675 halc_read(halcCLK, halcCS, halcDO);

// For the MAX6675 to update, you must delay AT LEAST 250ms between reads!
int temp_read_delay_milis = 250;
unsigned long t0 = 0;
unsigned long t = 0;

void types(String a) { Serial.println("it's a String"); }
void types(int a) { Serial.println("it's an int"); }
void types(char *a) { Serial.println("it's a char*"); }
void types(float a) { Serial.println("it's a float"); }
void types(bool a) { Serial.println("it's a bool"); }

void setup() {
  Serial.begin(115200);

  // wait for MAX chip to stabilize
  delay(1000);
  t0 = millis();
  main_t0 = t0;
  halc_t0 = t0;
 
  //turn the PID on
  main_temp_control.SetMode(AUTOMATIC);
  halc_temp_control.SetMode(AUTOMATIC);

  pinMode(main_pin, OUTPUT);
  pinMode(halc_pin, OUTPUT);
//  Serial.println("STARTING");
}

void loop() {
  t = millis();
  if ((t - t0) > temp_read_delay_milis){
    // basic readout test, just print the current temp
    main_temp = main_read.readCelsius();
    halc_temp = halc_read.readCelsius();
//    Serial.print(ar_flow); SejjjjjjSerial.println(",");
    t0 = millis();

//    main_temp_control.Compute();
//    halc_temp_control.Compute();
    if (internal_PID_control){
      main_temp_control.Compute();
      halc_temp_control.Compute();
    }

    dac.begin(addrs[0]);
    dac.setVoltage(4095*(ar_flow_setpoint/204.13), false);
    dac.begin(addrs[1]);
    dac.setVoltage(4095*(h2_flow_setpoint/20.52), false);

//    analogWrite(A3,halc_temp_output);
//    analogWrite(A4,main_temp_output);

    main_pwmDuty = main_temp_output;
    halc_pwmDuty = halc_temp_output;

    // PLACEHOLDER:
    // This should be replaced by actual reading of flow
    ar_flow = ar_flow_setpoint;
    h2_flow = h2_flow_setpoint;
  }

  //PWM STATE MAIN
  if (main_state == LOW) {
    if ((t - main_t0) >= (main_pwmPeriod*(1-main_pwmDuty))) {
      main_state = HIGH;
      if (main_pwmDuty > 0.1) {
        digitalWrite(main_pin, main_state);
      }
      main_t0 = millis();
    }
  } 
  if ((main_state == HIGH)) {
    if ((t - main_t0) > (main_pwmPeriod*(main_pwmDuty))) {
      main_state = LOW;
      if (main_pwmDuty < 0.9) {
        digitalWrite(main_pin, main_state);
      }
      main_t0 = millis();
    }
  }

  //PWM STATE SECONDARY
//  Serial.println(halc_pwmDuty);
  if (halc_state == LOW) {
    if ((t - halc_t0) >= (halc_pwmPeriod*(1-halc_pwmDuty))) {
      halc_state = HIGH;
      if (halc_pwmDuty > 0.1) {
        digitalWrite(halc_pin, halc_state);
      }
      halc_t0 = millis();
    }
  }
  if (halc_state == HIGH) {
    if ((t - halc_t0) >= (halc_pwmPeriod*(halc_pwmDuty))) {
      halc_state = LOW;
      if (halc_pwmDuty < 0.9) {
        digitalWrite(halc_pin, halc_state);
      }
      halc_t0 = millis();
    }
  }
}

void controlFurnace(char data[]){
  char * pch;
  char * category;
//  Serial.println(data);
  pch = strtok(data, ",");

  if (strcmp(pch, "get") == 0) {
//    Serial.println("GET triggered");
    Serial.print(ar_flow); Serial.print(",");
    Serial.print(h2_flow); Serial.print(",");
    Serial.print(main_temp); Serial.print(",");
    Serial.print(halc_temp); Serial.println(",");

  } else if (strcmp(pch, "set") == 0) {
    ar_flow_setpoint = atof(strtok(NULL, ","));
    h2_flow_setpoint = atof(strtok(NULL, ","));
    main_temp_setpoint = atof(strtok(NULL, ","));
    halc_temp_setpoint = atof(strtok(NULL, ","));
//    Serial.print(ar_flow_setpoint); Serial.print(" ");
//    Serial.print(h2_flow_setpoint); Serial.print(" ");
//    Serial.print(main_temp_setpoint); Serial.print(" ");
//    Serial.print(halc_temp_setpoint); Serial.println(" ");

  } else if (strcmp(pch, "set_direct") == 0) {
    //set_direct,3.5,5.5,125,255     ###furnace power is 0-255
    ar_flow_setpoint = atof(strtok(NULL, ","));
    h2_flow_setpoint = atof(strtok(NULL, ","));
    main_temp_output = atof(strtok(NULL, ","));
    halc_temp_output = atof(strtok(NULL, ","));
//    Serial.print(halc_temp_output); Serial.println(" ");
//    Serial.print(main_temp_output); Serial.println(" ");
//    Serial.print((int) halc_temp_output); Serial.println(" ");
//    Serial.print((int) main_temp_output); Serial.println(" ");

  } else if (strcmp(pch, "gains") == 0) {
    main_gains[0] = atof(strtok(NULL, ","));
    main_gains[1] = atof(strtok(NULL, ","));
    main_gains[2] = atof(strtok(NULL, ","));
    halc_gains[0] = atof(strtok(NULL, ","));
    halc_gains[1] = atof(strtok(NULL, ","));
    halc_gains[2] = atof(strtok(NULL, ","));
    main_temp_control.SetTunings(main_gains[0], main_gains[1], main_gains[2]);
    halc_temp_control.SetTunings(halc_gains[0], halc_gains[1], halc_gains[2]);
//    for (int i = 0; i<3; i++){
//      Serial.print(main_gains[i]);
//      Serial.print(" ");
//      Serial.print(halc_gains[i]); 
//      Serial.print(" | ");
//    }
//    Serial.println("");
  }
}

void serialEvent() {
  while(Serial.available()) {
    char current = Serial.read();
    if (current == '\r') {
      serbuff[ibuff] = '\0';
    } else if (current == '\n') {
      serbuff[ibuff] = '\0';
      ibuff = 0;
      controlFurnace(serbuff);
    } else {
      serbuff[ibuff] = current;
      ibuff++;
    }
  }
}
