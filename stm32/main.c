#include "stm32f10x.h"

/*
 * OLED self-test for the defect-sorting controller.
 * Connection: PB6 -> SCL, PB7 -> SDA, 3.3V -> VCC, GND -> GND.
 * This is a small software-I2C driver for the common 0.96-inch SSD1306 I2C OLED.
 */

#define OLED_ADDRESS  0x78U

static void delay_ms(uint32_t ms)
{
    volatile uint32_t count;
    while (ms--)
    {
        for (count = 0; count < 8000U; ++count)
        {
            __NOP();
        }
    }
}

static void led_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPCEN;
    GPIOC->CRH &= ~(GPIO_CRH_MODE13 | GPIO_CRH_CNF13);
    GPIOC->CRH |= GPIO_CRH_MODE13_1;
    GPIOC->BSRR = GPIO_BSRR_BS13;     /* PC13 onboard LED is active-low. */
}

static void i2c_delay(void)
{
    volatile uint32_t count;
    for (count = 0; count < 60U; ++count)
    {
        __NOP();
    }
}

static void oled_i2c_init(void)
{
    RCC->APB2ENR |= RCC_APB2ENR_IOPBEN;

    /* PB6/PB7: 2 MHz, general-purpose open-drain output. */
    GPIOB->CRL &= ~((0xFU << 24) | (0xFU << 28));
    GPIOB->CRL |=  ((0x6U << 24) | (0x6U << 28));
    GPIOB->BSRR = GPIO_BSRR_BS6 | GPIO_BSRR_BS7;
}

static void i2c_start(void)
{
    GPIOB->BSRR = GPIO_BSRR_BS6 | GPIO_BSRR_BS7;
    i2c_delay();
    GPIOB->BRR = GPIO_BRR_BR7;
    i2c_delay();
    GPIOB->BRR = GPIO_BRR_BR6;
}

static void i2c_stop(void)
{
    GPIOB->BRR = GPIO_BRR_BR6 | GPIO_BRR_BR7;
    i2c_delay();
    GPIOB->BSRR = GPIO_BSRR_BS6;
    i2c_delay();
    GPIOB->BSRR = GPIO_BSRR_BS7;
    i2c_delay();
}

static void i2c_write_byte(uint8_t value)
{
    uint8_t bit;
    for (bit = 0U; bit < 8U; ++bit)
    {
        if ((value & 0x80U) != 0U)
        {
            GPIOB->BSRR = GPIO_BSRR_BS7;
        }
        else
        {
            GPIOB->BRR = GPIO_BRR_BR7;
        }
        i2c_delay();
        GPIOB->BSRR = GPIO_BSRR_BS6;
        i2c_delay();
        GPIOB->BRR = GPIO_BRR_BR6;
        value <<= 1;
    }

    /* ACK clock. The simple OLED module always acknowledges; no read is needed. */
    GPIOB->BSRR = GPIO_BSRR_BS7;
    GPIOB->BSRR = GPIO_BSRR_BS6;
    i2c_delay();
    GPIOB->BRR = GPIO_BRR_BR6;
}

static void oled_write_command(uint8_t command)
{
    i2c_start();
    i2c_write_byte(OLED_ADDRESS);
    i2c_write_byte(0x00U);
    i2c_write_byte(command);
    i2c_stop();
}

static void oled_write_data(uint8_t data)
{
    i2c_start();
    i2c_write_byte(OLED_ADDRESS);
    i2c_write_byte(0x40U);
    i2c_write_byte(data);
    i2c_stop();
}

static void oled_set_cursor(uint8_t page, uint8_t column)
{
    oled_write_command((uint8_t)(0xB0U + page));
    oled_write_command((uint8_t)(0x00U + (column & 0x0FU)));
    oled_write_command((uint8_t)(0x10U + (column >> 4)));
}

static void oled_clear(void)
{
    uint8_t page;
    uint8_t column;
    for (page = 0U; page < 8U; ++page)
    {
        oled_set_cursor(page, 0U);
        for (column = 0U; column < 128U; ++column)
        {
            oled_write_data(0x00U);
        }
    }
}

static void oled_init(void)
{
    oled_i2c_init();
    delay_ms(100U);
    oled_write_command(0xAEU);
    oled_write_command(0x20U); oled_write_command(0x02U);
    oled_write_command(0x40U);
    oled_write_command(0xA1U);
    oled_write_command(0xC8U);
    oled_write_command(0x81U); oled_write_command(0x7FU);
    oled_write_command(0xA6U);
    oled_write_command(0xA8U); oled_write_command(0x3FU);
    oled_write_command(0xD3U); oled_write_command(0x00U);
    oled_write_command(0xD5U); oled_write_command(0x80U);
    oled_write_command(0xD9U); oled_write_command(0xF1U);
    oled_write_command(0xDAU); oled_write_command(0x12U);
    oled_write_command(0xDBU); oled_write_command(0x40U);
    oled_write_command(0x8DU); oled_write_command(0x14U);
    oled_write_command(0xAFU);
    oled_clear();
}

/* Seven 5-bit rows, used only for the capital letters needed by this self-test. */
static const uint8_t *glyph_rows(char character)
{
    static const uint8_t blank[7] = {0, 0, 0, 0, 0, 0, 0};
    static const uint8_t a[7] = {14, 17, 17, 31, 17, 17, 17};
    static const uint8_t c[7] = {14, 17, 16, 16, 16, 17, 14};
    static const uint8_t d[7] = {30, 17, 17, 17, 17, 17, 30};
    static const uint8_t e[7] = {31, 16, 16, 30, 16, 16, 31};
    static const uint8_t f[7] = {31, 16, 16, 30, 16, 16, 16};
    static const uint8_t l[7] = {16, 16, 16, 16, 16, 16, 31};
    static const uint8_t m[7] = {17, 27, 21, 21, 17, 17, 17};
    static const uint8_t o[7] = {14, 17, 17, 17, 17, 17, 14};
    static const uint8_t p[7] = {30, 17, 17, 30, 16, 16, 16};
    static const uint8_t r[7] = {30, 17, 17, 30, 20, 18, 17};
    static const uint8_t s[7] = {15, 16, 16, 14, 1, 1, 30};
    static const uint8_t t[7] = {31, 4, 4, 4, 4, 4, 4};
    static const uint8_t u[7] = {17, 17, 17, 17, 17, 17, 14};
    static const uint8_t y[7] = {17, 17, 10, 4, 4, 4, 4};

    switch (character)
    {
        case 'A': return a; case 'C': return c; case 'D': return d;
        case 'E': return e; case 'F': return f; case 'L': return l;
        case 'M': return m; case 'O': return o; case 'P': return p;
        case 'R': return r; case 'S': return s; case 'T': return t;
        case 'U': return u; case 'Y': return y;
        default:  return blank;
    }
}

static void oled_show_text(uint8_t page, uint8_t column, const char *text)
{
    const uint8_t *rows;
    uint8_t x;
    uint8_t y;
    uint8_t dots;

    oled_set_cursor(page, column);
    while (*text != '\0')
    {
        rows = glyph_rows(*text++);
        for (x = 0U; x < 5U; ++x)
        {
            dots = 0U;
            for (y = 0U; y < 7U; ++y)
            {
                if ((rows[y] & (uint8_t)(1U << (4U - x))) != 0U)
                {
                    dots |= (uint8_t)(1U << y);
                }
            }
            oled_write_data(dots);
        }
        oled_write_data(0x00U);
    }
}

int main(void)
{
    led_init();
    oled_init();

    oled_show_text(1U, 14U, "DEFECT DETECTOR");
    oled_show_text(3U, 26U, "SYSTEM READY");
    oled_show_text(5U, 22U, "OLED TEST PASS");

    while (1)
    {
        /* The next step will replace this idle state with PC serial commands. */
    }
}
