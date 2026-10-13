#pragma once // #progma once est utiliser a la place des include guard que j'ai mis 
// en commentaire ci dessous
/*
#ifndef GY_BNO055_HPP
#define GY_BNO055_HPP

class GY_BNO055 {
public:
  void begin();
};

#endif // GY_BNO055_HPP  
*/

#include <Arduino.h>
#include <Wire.h>

class GY_BNO055 {
public:
  struct Vector3 {
    float x;
    float y;
    float z;
  };

  struct Quaternion {
    float w;
    float x;
    float y;
    float z;
  };

  enum class OprMode : uint8_t {
    CONFIGMODE = 0x00,
    ACCONLY    = 0x01,
    MAGONLY    = 0x02,
    GYRONLY    = 0x03,
    ACCMAG     = 0x04,
    ACCGYRO    = 0x05,
    MAGGYRO    = 0x06,
    AMG        = 0x07,
    IMUPLUS    = 0x08,
    COMPASS    = 0x09,
    M4G        = 0x0A,
    NDOF_FMC_OFF = 0x0B,
    NDOF       = 0x0C
  };

  GY_BNO055();

  // I2C init + capteur init (initialisation du capteur BNO055)

  bool begin(TwoWire &wire = Wire, uint8_t i2cAddr = 0x28, int sda = -1, int scl = -1, uint32_t freq = 400000);

  // Optionnel : changer le mode de fusion
  bool setMode(OprMode mode);

  // Lectures principales
  bool readAccelMS2(Vector3 &out);     // m/s^2 (linéarité non retirée; c'est accel "sensor")
  bool readLinAccelMS2(Vector3 &out);  // m/s^2 (accel linéaire, gravité retirée)
  bool readGravityMS2(Vector3 &out);   // m/s^2 Donne le vecteur gravité estimé (utile pour inclinaison, pose).
  bool readGyroDPS(Vector3 &out);      // deg/s Lit vitesse angulaire en degrés/s.
  bool readMagUT(Vector3 &out);        // microTesla Lit champ magnétique en microTesla (uT).
  bool readEulerDeg(Vector3 &out);     // deg: lire l'orientation en angle d'euler heading(yaw), roll, pitch (ordre BNO)
  bool readQuaternion(Quaternion &q);  // quaternion normalisé

  // Statut/calibration du capteur BNO055 
  bool getCalibrationStatus(uint8_t &sys, uint8_t &gyro, uint8_t &accel, uint8_t &mag);
  // Renvoie les niveaux de calibration : 0..3 pour chaque capteur.
  // Important pour savoir si les mesures sont fiables.

  bool getSystemStatus(uint8_t &sysStatus, uint8_t &selfTest, uint8_t &sysError);
  // Renvoie le statut système, résultat self-test, code erreur système.

  // Détection “capteur présent”
  uint8_t address() const { return _addr; }
  // Renvoie l'adresse I2C utilisée (0x28 ou 0x29)

private:
  // Pointeur vers le bus I2C utilisé (Wire). nullptr = pas encore initialisé.
  TwoWire *_wire = nullptr;
  // Adresse I2C utilisée
  uint8_t _addr = 0x28;

  bool checkChipId(); // vérifie la présence du BNO055
  bool write8(uint8_t reg, uint8_t val); // écriture 1 octet
  bool read8(uint8_t reg, uint8_t &val); // lecture 1 octet
  bool readLen(uint8_t reg, uint8_t *buf, size_t len); // lecture multiple octets

  // conversions
  static int16_t u8ToS16(uint8_t lsb, uint8_t msb) { return (int16_t)((msb << 8) | lsb); }
  /*
  Le capteur renvoie souvent une valeur sur 2 octets (LSB/MSB).
  msb << 8 décale le MSB de 8 bits, puis | lsb ajoute le LSB.
  On cast en int16_t pour avoir les valeurs négatives possibles.
  */

  bool setConfigMode();
  bool setOperationMode(OprMode mode);
  // Fonctions internes utilisées par begin() et setMode() pour passer proprement d’un mode à l’autre.

  // registres BNO055
  static constexpr uint8_t REG_CHIP_ID       = 0x00; // Adresse du registre CHIP_ID. constexpr = valeur compile-time (pas de RAM utilisée).
  static constexpr uint8_t CHIP_ID           = 0xA0; // Valeur attendue du CHIP_ID pour BNO055.
  static constexpr uint8_t REG_PAGE_ID       = 0x07; // page des registres (0 ou 1)
  static constexpr uint8_t REG_OPR_MODE      = 0x3D; // mode opération
  static constexpr uint8_t REG_PWR_MODE      = 0x3E; // mode puissance
  static constexpr uint8_t REG_SYS_TRIGGER   = 0x3F; // trigger système
  static constexpr uint8_t REG_TEMP_SOURCE   = 0x40; // source température
  static constexpr uint8_t REG_CALIB_STAT    = 0x35; // statut calibration
  static constexpr uint8_t REG_SYS_STATUS    = 0x39; // statut système
  static constexpr uint8_t REG_SELFTEST_RES  = 0x36; // résultat self-test
  static constexpr uint8_t REG_SYS_ERR       = 0x3A; // code erreur système

  // data registers
  static constexpr uint8_t REG_ACC_DATA_X_LSB = 0x08; // 6 bytes
  static constexpr uint8_t REG_MAG_DATA_X_LSB = 0x0E; // 6 bytes
  static constexpr uint8_t REG_GYR_DATA_X_LSB = 0x14; // 6 bytes
  static constexpr uint8_t REG_EUL_DATA_X_LSB = 0x1A; // 6 bytes
  static constexpr uint8_t REG_QUA_DATA_W_LSB = 0x20; // 8 bytes
  static constexpr uint8_t REG_LIA_DATA_X_LSB = 0x28; // 6 bytes
  static constexpr uint8_t REG_GRV_DATA_X_LSB = 0x2E; // 6 bytes
};

/*
constexpr signifie : “cette valeur est connue à la compilation”.
Autrement dit :
Le compilateur calcule la valeur avant même que le programme ne tourne.
Rôle de chaque mot :
static → appartient à la classe, pas à l’objet
constexpr → connu à la compilation
uint8_t → type
= 0x08 → valeur
Une seule copie globale, zéro RAM, zéro overhead
*/