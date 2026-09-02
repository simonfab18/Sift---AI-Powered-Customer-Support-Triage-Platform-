import { Suspense } from "react";
import { VerifyEmailPage } from "@/components/sift/AuthPage";

export default function Page() {
  return <Suspense fallback={null}><VerifyEmailPage /></Suspense>;
}



