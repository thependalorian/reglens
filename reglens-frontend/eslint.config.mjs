import next from "eslint-config-next";

const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**", ".agents/**", "next-env.d.ts"],
  },
  ...next,
];

export default eslintConfig;
