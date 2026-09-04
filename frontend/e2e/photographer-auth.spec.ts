import { test, expect } from '@playwright/test';

test.describe('Photographer Flow', () => {
  test('should login and view dashboard', async ({ page }) => {
    // Navigate to login
    await page.goto('/login');
    
    // Fill in credentials
    await page.fill('input[name="email"]', 'admin@spotme.com');
    await page.fill('input[name="password"]', 'Password123!');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Verify successful login redirect to dashboard
    await expect(page).toHaveURL('/dashboard/events');
    await expect(page.locator('h1')).toContainText('Events');
    
    // Create new event
    await page.click('button:has-text("Create Event")');
    
    // Fill out create event form
    await page.fill('input[name="name"]', 'My E2E Event');
    await page.fill('#dateStart', '2026-12-31');
    await page.click('button[type="submit"]');
    
    // Should redirect to the new event detail page
    await expect(page).toHaveURL(/\/dashboard\/events\/.+/);
    await expect(page.locator('h1')).toContainText('My E2E Event');
  });
});
