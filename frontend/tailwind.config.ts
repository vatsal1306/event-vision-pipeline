import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#F3F0EE",
        lifted: "#FCFBFA",
        ink: "#141413",
        signal: "#CF4500",
        "signal-light": "#F37338",
      },
      borderRadius: {
        button: "20px",
        stadium: "40px",
        pill: "999px",
      },
      fontFamily: {
        sans: ["var(--font-sofia-sans)", "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
