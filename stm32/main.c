#include "stm32f10x.h"

/* Blue Pill boards normally connect the onboard LED to PC13 (active low). */
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
    GPIOC->BSRR = GPIO_BSRR_BS13;
}

int main(void)
{
    led_init();

    while (1)
    {
        GPIOC->BRR = GPIO_BRR_BR13;
        delay_ms(500);
        GPIOC->BSRR = GPIO_BSRR_BS13;
        delay_ms(500);
    }
}
