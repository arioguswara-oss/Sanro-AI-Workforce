export const TRUSTED_CHROMIUM_EXECUTABLE = '/usr/local/lib/sanro-playwright/chromium-1255/chrome-linux64/chrome';

export function buildPrivateBrowserRuntimeConfig(config, executablePath) {
  if (!config || typeof config !== 'object' || executablePath !== TRUSTED_CHROMIUM_EXECUTABLE) {
    throw new Error('private browser requires the fixed approved Chromium executable');
  }
  if (config.browser?.browserName !== 'chromium' || config.browser?.launchOptions?.chromiumSandbox !== true) {
    throw new Error('private browser profile must select Chromium with chromiumSandbox=true');
  }
  return {
    ...config,
    browser: {
      ...config.browser,
      launchOptions: { ...config.browser.launchOptions, chromiumSandbox: true, executablePath: TRUSTED_CHROMIUM_EXECUTABLE },
    },
  };
}
