/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "usb_device.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "ssd1306.h"
#include "fonts.h"
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

/* USER CODE BEGIN PV */
	char usb_rx_buffer[64] = {0}; // Сюда будут падать данные от Python
	volatile uint8_t usb_rx_flag = 0;      // Флаг, что пришли новые данные
	int logi_bat = 0;             // Заряд мыши
	int audeze_bat = 0;           // Заряд наушников
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_I2C1_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
		
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_I2C1_Init();
  MX_USB_DEVICE_Init();
  /* USER CODE BEGIN 2 */
		
	SSD1306_Init(); // Обязательно включаем экран
	ssd1306_I2C_Write(SSD1306_I2C_ADDR, 0x00, 0xA0);
	ssd1306_I2C_Write(SSD1306_I2C_ADDR, 0x00, 0xC0);
  SSD1306_Fill(0); // Очищаем экран черным цветом (0)
  
  uint8_t is_connected = 0;          // Флаг получения первого пакета
  uint32_t last_loading_time = 0;    // Таймер для анимации
  uint8_t loading_dots = 0;          // Количество точек (0-3)
  int logi_charge_state = -1;
  int audeze_charge_state = -1;
  
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
      
      // ==========================================
      // 1. АНИМАЦИЯ ОЖИДАНИЯ (Пока нет данных)
      // ==========================================
      if (is_connected == 0) 
      {
          if (HAL_GetTick() - last_loading_time > 400) { // Обновление каждые 400 мс
              last_loading_time = HAL_GetTick();
              loading_dots++;
              if (loading_dots > 3) loading_dots = 0;
              
              SSD1306_Fill(0); // Очищаем экран
              
              // Рисуем стильную рамку по краям экрана
              SSD1306_DrawRectangle(0, 0, 128, 64, 1);
              
              // Анимируем точки
              SSD1306_GotoXY(30, 26);
              if (loading_dots == 0) SSD1306_Puts("LOADING   ", &Font_7x10, 1);
              if (loading_dots == 1) SSD1306_Puts("LOADING.  ", &Font_7x10, 1);
              if (loading_dots == 2) SSD1306_Puts("LOADING.. ", &Font_7x10, 1);
              if (loading_dots == 3) SSD1306_Puts("LOADING...", &Font_7x10, 1);
              
              SSD1306_UpdateScreen();
          }
      }

      // ==========================================
      // 2. ОБРАБОТКА ДАННЫХ И ОТРИСОВКА ДАШБОРДА
      // ==========================================
      if (usb_rx_flag == 1) 
      {
          char time_str[10] = {0};
          char weather_str[10] = {0};

          // L/A - проценты, LC/AC - зарядка: 1 = да, 0 = нет, -1 = неизвестно
          int parsed = sscanf(
              usb_rx_buffer,
              "L%d LC%d A%d AC%d T%9s W%9s",
              &logi_bat,
              &logi_charge_state,
              &audeze_bat,
              &audeze_charge_state,
              time_str,
              weather_str
          );

          if (parsed != 6) {
              usb_rx_flag = 0;
              continue;
          }

          is_connected = 1; // Успешно получили данные, выключаем анимацию загрузки
          
          SSD1306_Fill(0); // Очищаем буфер дисплея
          
          // --- Массивы пикселей для иконок (10x10) ---
          const uint8_t icon_mouse[10][10] = {
              {0,0,0,1,1,1,1,0,0,0}, {0,0,1,0,0,0,0,1,0,0}, {0,1,0,0,1,1,0,0,1,0},
              {0,1,0,0,1,1,0,0,1,0}, {0,1,0,0,0,0,0,0,1,0}, {0,1,0,0,0,0,0,0,1,0},
              {0,1,0,0,0,0,0,0,1,0}, {0,0,1,0,0,0,0,1,0,0}, {0,0,0,1,1,1,1,0,0,0},
              {0,0,0,0,0,0,0,0,0,0}
          };
          
          const uint8_t icon_head[10][10] = {
              {0,0,1,1,1,1,1,1,0,0}, {0,1,0,0,0,0,0,0,1,0}, {1,0,0,0,0,0,0,0,0,1},
              {1,0,0,0,0,0,0,0,0,1}, {1,1,1,0,0,0,0,1,1,1}, {1,1,1,0,0,0,0,1,1,1},
              {1,1,1,0,0,0,0,1,1,1}, {0,1,0,0,0,0,0,0,1,0}, {0,0,0,0,0,0,0,0,0,0},
              {0,0,0,0,0,0,0,0,0,0}
          };

          // Значок молнии (4x8), отображается только при активной зарядке
          const uint8_t icon_charge[8][4] = {
              {0,0,1,1},
              {0,1,1,0},
              {0,1,1,0},
              {1,1,1,1},
              {0,0,1,1},
              {0,0,1,0},
              {0,1,1,0},
              {0,1,0,0}
          };
          
          // Отрисовка иконок слева
          for(int y = 0; y < 10; y++) {
              for(int x = 0; x < 10; x++) {
                  if(icon_mouse[y][x]) SSD1306_DrawPixel(2 + x, 5 + y, 1);
                  if(icon_head[y][x])  SSD1306_DrawPixel(2 + x, 25 + y, 1);
              }
          }
          
          // --- Вывод текстовых процентов справа (С ЗАЩИТОЙ ОТ НУЛЕЙ) ---
          char str_logi_val[10];
          char str_aud_val[10];
          char str_bottom[32];
          
          // Текстовая логика для мыши (0 = спит/нет данных)
          if (logi_bat <= 0) {
              sprintf(str_logi_val, " --%%");
          } else {
              sprintf(str_logi_val, "%d%%", logi_bat);
          }
          
          // Текстовая логика для наушников (-1 = защита, 0 = спит)
          if (audeze_bat < 0) {
              sprintf(str_aud_val, " "); // Оставляем пустым, текст заглушки будет на месте батареи
          } else if (audeze_bat == 0) {
              sprintf(str_aud_val, " --%%");
          } else {
              sprintf(str_aud_val, "%d%%", audeze_bat);
          }
          
          SSD1306_GotoXY(88, 5);
          SSD1306_Puts(str_logi_val, &Font_7x10, 1);
          
          SSD1306_GotoXY(88, 25);
          SSD1306_Puts(str_aud_val, &Font_7x10, 1);

          // Молнии справа от процентов: верхняя — мышь, нижняя — наушники
          for (int y = 0; y < 8; y++) {
              for (int x = 0; x < 4; x++) {
                  if (icon_charge[y][x]) {
                      if (logi_charge_state == 1) {
                          SSD1306_DrawPixel(121 + x, 6 + y, 1);
                      }
                      if (audeze_charge_state == 1) {
                          SSD1306_DrawPixel(121 + x, 26 + y, 1);
                      }
                  }
              }
          }
          
          // --- Отрисовка графических батареек ---
          int bat_x = 18;
          
          // 1. Батарейка мыши
          int bat_y = 5;
          for(int x = 0; x < 50; x++) {
              for(int y = 0; y < 10; y++) {
                  if (x == 0 || x == 49 || y == 0 || y == 9) {
                      SSD1306_DrawPixel(bat_x + x, bat_y + y, 1);
                  }
              }
          }
          SSD1306_DrawPixel(bat_x + 50, bat_y + 3, 1);
          SSD1306_DrawPixel(bat_x + 50, bat_y + 4, 1);
          SSD1306_DrawPixel(bat_x + 50, bat_y + 5, 1);
          SSD1306_DrawPixel(bat_x + 50, bat_y + 6, 1);
          
          // Заливка полосы заряда (только если > 0)
          if (logi_bat > 0) {
              int logi_fill = (logi_bat * 46) / 100;
              if (logi_fill > 46) logi_fill = 46;
              for(int x = 2; x < 2 + logi_fill; x++) {
                  for(int y = 2; y < 8; y++) {
                      SSD1306_DrawPixel(bat_x + x, bat_y + y, 1);
                  }
              }
          }

          // 2. Батарейка наушников
          bat_y = 25;
          if (audeze_bat < 0) {
              // Выводим нашу стильную заглушку вместо контура батареи
              SSD1306_GotoXY(bat_x - 3, bat_y + 1); 
              SSD1306_Puts("USE AUD HQ", &Font_7x10, 1);
          } else {
              for(int x = 0; x < 50; x++) {
                  for(int y = 0; y < 10; y++) {
                      if (x == 0 || x == 49 || y == 0 || y == 9) {
                          SSD1306_DrawPixel(bat_x + x, bat_y + y, 1);
                      }
                  }
              }
              SSD1306_DrawPixel(bat_x + 50, bat_y + 3, 1);
              SSD1306_DrawPixel(bat_x + 50, bat_y + 4, 1);
              SSD1306_DrawPixel(bat_x + 50, bat_y + 5, 1);
              SSD1306_DrawPixel(bat_x + 50, bat_y + 6, 1);
              
              // Заливка полосы заряда (только если > 0)
              if (audeze_bat > 0) {
                  int aud_fill = (audeze_bat * 46) / 100;
                  if (aud_fill > 46) aud_fill = 46;
                  for(int x = 2; x < 2 + aud_fill; x++) {
                      for(int y = 2; y < 8; y++) {
                          SSD1306_DrawPixel(bat_x + x, bat_y + y, 1);
                      }
                  }
              }
          }

          // --- Подвал (Разделитель, время и погода) ---
          SSD1306_GotoXY(0, 35);
          SSD1306_Puts("__________________", &Font_7x10, 1);

          int len = sprintf(str_bottom, "Time:%s  %s", time_str, weather_str);
          
          SSD1306_GotoXY(2, 52);
          SSD1306_Puts(str_bottom, &Font_7x10, 1);
          
          int deg_x = 2 + (len * 7); 
          int deg_y = 52; 
          
          SSD1306_DrawPixel(deg_x, deg_y, 1);
          SSD1306_DrawPixel(deg_x + 1, deg_y, 1);
          SSD1306_DrawPixel(deg_x, deg_y + 1, 1);
          SSD1306_DrawPixel(deg_x + 1, deg_y + 1, 1);
          
          SSD1306_GotoXY(deg_x + 3, 52);
          SSD1306_Puts("C", &Font_7x10, 1);
          
          // Отправка кадра в дисплей и сброс флага приема
          SSD1306_UpdateScreen();
          usb_rx_flag = 0;
      }
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE2);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 15;
  RCC_OscInitStruct.PLL.PLLN = 144;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
  RCC_OscInitStruct.PLL.PLLQ = 5;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 400000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
