import { cx } from "./cx";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger";
};

const variants = {
  primary: "border border-[#756f9f] bg-[#756f9f] text-white shadow-sm shadow-slate-900/5 hover:bg-[#625d86] disabled:border-slate-300 disabled:bg-slate-300",
  outline: "border border-slate-300 bg-white text-slate-800 shadow-sm shadow-slate-900/5 hover:border-slate-400 hover:bg-slate-50 disabled:text-slate-400",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:text-slate-400",
  danger: "border border-[#d8d2e4] bg-white/60 text-[#6f6174] shadow-sm shadow-slate-900/5 hover:bg-white/75 disabled:text-slate-400",
};

export function Button({ className, variant = "outline", ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed",
        variants[variant],
        className,
      )}
    />
  );
}




