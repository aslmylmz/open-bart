import type { LucideIcon, LucideProps } from "lucide-react";

interface IconProps extends LucideProps {
  /** A lucide glyph, named-imported by the caller so the build stays
   * tree-shaken and offline (ADR 0002), e.g. `<Icon icon={FolderOpen} />`. */
  icon: LucideIcon;
}

/** Chrome icons at the instrument's one optical weight (DESIGN-SPEC §1.4):
 * 16px box, 1.5px stroke. Decorative by default — pass aria-label (and drop
 * aria-hidden) where a glyph carries meaning on its own. */
export function Icon({ icon: Glyph, size = 16, strokeWidth = 1.5, ...props }: IconProps) {
  return <Glyph aria-hidden size={size} strokeWidth={strokeWidth} {...props} />;
}
