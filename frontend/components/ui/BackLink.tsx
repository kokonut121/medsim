import type { Route } from "next";
import Link from "next/link";

interface BackLinkProps {
  href: Route;
  label: string;
}

export function BackLink({ href, label }: BackLinkProps) {
  return (
    <Link className="back-link" href={href}>
      <span className="back-link__arrow" aria-hidden="true">
        ←
      </span>
      <span className="back-link__label">{label}</span>
    </Link>
  );
}
