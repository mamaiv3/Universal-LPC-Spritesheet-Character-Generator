// Global state and state operations
import m from "mithril";
import { LICENSE_CONFIG, ANIMATIONS, BODY_TYPES } from "./constants.ts";
import { syncSelectionsToHash, loadSelectionsFromHash } from "./hash.ts";
import type { CatalogReader, ItemMerged } from "./catalog.ts";
import { renderCharacter } from "../canvas/renderer.ts";

/** A single item selection within a selection group (e.g. body, head, ears). */
export type Selection = {
  itemId: string;
  name: string;
  /** Index into the item's `recolors` array; `null` for top-level selections. */
  subId?: number | null;
  /** Set when the item exposes `variants`. Empty string represents "default". */
  variant?: string | null;
  /** Set when the item exposes `recolors`. Empty string represents "default". */
  recolor?: string | null;
};

/** All selections, keyed by selection group (`type_name` of the item or recolor slot). */
export type Selections = Record<string, Selection>;

/**
 * State.ts treats catalog metadata defensively — fields like `type_name` are
 * narrowed at each access. Modeling the DI return as `Partial<ItemMerged>`
 * matches that style and keeps test stubs (which supply only the fields they
 * exercise) typeable from JS.
 */
type MetadataView = Partial<ItemMerged>;

type ZipMode = { isRunning: boolean };

/** Global application state. Mutated in place; Mithril views observe via redraw. */
export type State = {
  // saved in URL hash
  selections: Selections;
  bodyType: string;

  // potentially saved in future
  selectedAnimation: string;
  expandedNodes: Record<string, boolean>;
  searchQuery: string;
  showTransparencyGrid: boolean;
  applyTransparencyMask: boolean;
  matchBodyColorEnabled: boolean;
  compactDisplay: boolean;
  customUploadedImage: HTMLImageElement | null;
  customImageZPos: number;
  previewCanvasZoomLevel: number;
  fullSpritesheetCanvasZoomLevel: number;
  /** True after `main.ts` runs the first bootstrap `renderCharacter`. */
  previewBootstrapRenderDone: boolean;
  /** Mirrored from `renderCharacter` compositing (see `renderer.ts`). */
  isRenderingCharacter: boolean;
  enabledLicenses: Record<string, boolean>;
  enabledAnimations: Record<string, boolean>;

  // transient (never saved)
  zipByAnimation: ZipMode;
  zipByItem: ZipMode;
  zipByAnimationAndItem: ZipMode;
  zipIndividualFrames: ZipMode;
  /** Duplicate of `isRenderingCharacter` consumed by `renderer.ts`. */
  renderCharacter: { isRendering: boolean };
};

type StateDeps = {
  getItemMetadata: (itemId: string) => MetadataView | null;
  selectDefaults: (state: State) => Promise<void>;
  redraw: () => void;
  syncSelectionsToHash: (state: State) => void;
  renderCharacter: (
    state: State,
    selections: Selections,
    bodyType: string,
  ) => Promise<void>;
  loadSelectionsFromHash: (state: State) => void;
  getCanvasRenderer: () => unknown;
};

// Application bootstrap supplies the catalog; tests may override individual effects.
let configuredCatalog: CatalogReader | undefined;

function createDefaultStateDeps(catalog: CatalogReader): StateDeps {
  return {
    getItemMetadata: (itemId) => catalog.getItemMerged(itemId).unwrapOr(null),
    selectDefaults,
    redraw: () => m.redraw(),
    syncSelectionsToHash: (state) => syncSelectionsToHash(catalog, state),
    renderCharacter: (state, selections, bodyType) =>
      renderCharacter(catalog, state, selections, bodyType),
    loadSelectionsFromHash: (state) => loadSelectionsFromHash(catalog, state),
    getCanvasRenderer: () =>
      (window as unknown as { canvasRenderer?: unknown }).canvasRenderer,
  };
}

let stateDeps: StateDeps | undefined;

/** Bind state operations to the catalog owned by application bootstrap. */
export function configureStateCatalog(catalog: CatalogReader): void {
  configuredCatalog = catalog;
  stateDeps = createDefaultStateDeps(catalog);
}

export function setStateDeps(overrides: Partial<StateDeps>): void {
  Object.assign(getStateDeps(), overrides);
}

export function resetStateDeps(): void {
  if (!configuredCatalog) {
    throw new Error(
      "State catalog is not configured; call configureStateCatalog(catalog) before resetting dependencies",
    );
  }
  stateDeps = createDefaultStateDeps(configuredCatalog);
}

export function getStateDeps(): StateDeps {
  if (!stateDeps) {
    throw new Error(
      "State catalog is not configured; call configureStateCatalog(catalog) during bootstrap",
    );
  }
  return stateDeps;
}

// Global state
export function createState(): State {
  return {
    // state that is saved in url hash
    selections: {},
    bodyType: BODY_TYPES[0],

    // State that is currently not saved but could be in future
    selectedAnimation: "walk",
    expandedNodes: {},
    searchQuery: "",
    showTransparencyGrid: true,
    applyTransparencyMask: false,
    matchBodyColorEnabled: true,
    compactDisplay: false,
    customUploadedImage: null,
    customImageZPos: 0,
    previewCanvasZoomLevel: 1,
    fullSpritesheetCanvasZoomLevel: 1,
    previewBootstrapRenderDone: false,
    isRenderingCharacter: false,
    enabledLicenses: Object.fromEntries(
      LICENSE_CONFIG.map((lic) => [lic.key, true]),
    ),
    enabledAnimations: Object.fromEntries(
      ANIMATIONS.map((anim) => [anim.value, false]),
    ),

    // Following transient state should never be saved
    zipByAnimation: { isRunning: false },
    zipByItem: { isRunning: false },
    zipByAnimationAndItem: { isRunning: false },
    zipIndividualFrames: { isRunning: false },
    renderCharacter: { isRendering: false },
  };
}

/**
 * Selection group = `type_name` (e.g. "body", "heads", "ears"). Ensures only
 * one item per type can be selected (mimics legacy radio-button behavior).
 */
export function getSelectionGroup(itemId: string): string {
  const meta = getStateDeps().getItemMetadata(itemId);
  if (!meta || !meta.type_name) return itemId;
  return meta.type_name;
}

/** Sub-selection group for a recolor option; falls back to the item's type_name. */
export function getSubSelectionGroup(itemId: string, idx: number): string {
  const meta = getStateDeps().getItemMetadata(itemId);
  const recolor = meta?.recolors?.[idx];
  if (!meta || !meta.type_name) return itemId;
  return recolor?.type_name ?? meta.type_name;
}

// Select default items (body color light + human male light head)
export async function selectDefaults(state: State): Promise<void> {
  const deps = getStateDeps();
  // itemId is now based on filename (e.g., "body").
  const bodyItemId = "body";
  const bodySelectionGroup = getSelectionGroup(bodyItemId);
  state.selections[bodySelectionGroup] = {
    itemId: bodyItemId,
    variant: "",
    recolor: "light",
    name: "Body color (light)",
  };

  const headItemId = "heads_human_male";
  const headSelectionGroup = getSelectionGroup(headItemId);
  state.selections[headSelectionGroup] = {
    itemId: headItemId,
    variant: "",
    recolor: "light",
    name: "Human Male (light)",
  };

  const expressionItemId = "face_neutral";
  const expressionSelectionGroup = getSelectionGroup(expressionItemId);
  state.selections[expressionSelectionGroup] = {
    itemId: expressionItemId,
    variant: "",
    recolor: "light",
    name: "Neutral (light)",
  };

  deps.syncSelectionsToHash(state);
  await deps.renderCharacter(state, state.selections, state.bodyType);
  // Trigger redraw to update preview canvas after offscreen render completes
  deps.redraw();
}

export async function resetAll(state: State): Promise<void> {
  const deps = getStateDeps();
  state.selections = {};
  state.customUploadedImage = null;
  state.customImageZPos = 0;
  await deps.selectDefaults(state);
  deps.redraw();
}

/** When any body-colored part changes, propagate variant/recolor to other items with matchBodyColor. */
export function applyMatchBodyColor(
  state: State,
  variantToMatch: string | null,
  recolorToMatch: string | null,
): void {
  const deps = getStateDeps();
  if (!state.matchBodyColorEnabled) return;
  if (!variantToMatch && !recolorToMatch) return;

  for (const selection of Object.values(state.selections)) {
    const itemId = selection.itemId;
    const meta = deps.getItemMetadata(itemId);

    if (!meta || !meta.matchBodyColor) continue;

    if (
      selection.subId !== null &&
      selection.subId !== undefined &&
      !meta.recolors?.[selection.subId]?.matchBodyColor
    )
      continue;

    if (variantToMatch && meta.variants?.includes(variantToMatch)) {
      selection.variant = variantToMatch;
      selection.name = `${meta.name} (${variantToMatch})`;
    }

    if (
      recolorToMatch &&
      meta.recolors?.[0]?.variants?.includes(recolorToMatch)
    ) {
      selection.recolor = recolorToMatch;
      selection.name = `${meta.name} (${recolorToMatch})`;
    }
  }
}

export async function initState(state: State): Promise<void> {
  const deps = getStateDeps();
  deps.loadSelectionsFromHash(state);

  if (Object.keys(state.selections).length === 0) {
    await deps.selectDefaults(state);
  } else if (deps.getCanvasRenderer()) {
    await deps.renderCharacter(state, state.selections, state.bodyType);
    deps.redraw();
  }
}

export function selectItem(
  state: State,
  itemId: string,
  variant: string,
  isSelected: boolean = false,
  subId: number | null = null,
): void {
  const deps = getStateDeps();
  const selectionGroup = getSelectionGroup(itemId);
  const subSelect =
    subId !== null ? getSubSelectionGroup(itemId, subId) : selectionGroup;

  if (isSelected) {
    delete state.selections[subSelect];
    return;
  }

  const meta = deps.getItemMetadata(itemId);
  if (!meta) return;

  const useVariants = (meta.variants?.length ?? 0) > 0;
  const variantDisplayName = variant.replaceAll("_", " ");

  const subMeta =
    !useVariants && subId !== null ? meta.recolors?.[subId] : null;
  const displayName = subMeta?.type_name ? subMeta.label : meta.name;

  state.selections[subSelect] = {
    itemId,
    subId: subMeta?.type_name ? subId : null,
    variant: useVariants ? variant : null,
    recolor: useVariants ? null : variant,
    name: `${displayName} (${variantDisplayName})`,
  };

  if (subMeta?.type_name && subSelect !== selectionGroup) {
    const existingParent = state.selections[selectionGroup];
    if (existingParent) {
      const parentRecolor = existingParent.recolor;
      state.selections[selectionGroup] = {
        itemId,
        subId: null,
        variant: existingParent.variant,
        recolor: parentRecolor,
        name: `${meta.name}${parentRecolor ? ` (${parentRecolor.replaceAll("_", " ")})` : ""}`,
      };
    }
  }

  if (
    subMeta?.matchBodyColor ||
    (subSelect === selectionGroup && meta.matchBodyColor)
  ) {
    applyMatchBodyColor(state, variant, !useVariants ? variant : null);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Random Human Maker — FINAL FIX
// catalog rows use type_name (not typeName).
// ─────────────────────────────────────────────────────────────────────────────

type RandomHumanMode = "human" | "male" | "female" | "villager";

const HUMAN_CATEGORIES = [
  ["body", "body color", "shadow"],
  ["head", "heads"],
  ["face", "faces"],
  ["ear", "ears"],
  ["nose"],
  ["wrinkle", "wrinkles"],
  ["hair"],
  ["headwear", "hat"],
  ["arm", "arms"],
  ["torso"],
  ["leg", "legs"],
  ["feet", "foot"],
  ["tool", "tools"],
] as const;

const BAD_RANDOM =
  /alien|cyclops|special.?eyes|one.?eye|orc|goblin|dragon|monster|animal|zombie|skeleton|undead|tentacle/i;

function pickRandom<T>(items: T[]): T | null {
  return items.length ? items[Math.floor(Math.random() * items.length)] : null;
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[_-]/g, " ").trim();
}

function itemText(item: any): string {
  return normalize(`${item.itemId ?? ""} ${item.name ?? ""} ${item.type_name ?? ""}`);
}

function matchesCategory(groupName: string, item: any, aliases: readonly string[]): boolean {
  const group = normalize(groupName);
  const type = normalize(item.type_name ?? "");
  return aliases.some(a => {
    const alias = normalize(a);
    return group === alias || type === alias ||
      group.includes(alias) || type.includes(alias);
  });
}

function getVariant(item: any): string | null {
  const variants = item.variants?.length
    ? item.variants
    : (item.recolors?.flatMap((r: any) => r.variants ?? []) ?? []);
  return pickRandom(variants);
}

function getAllCategoryItems(indexes: any, aliases: readonly string[]): any[] {
  return (Object.entries(indexes.byTypeName) as [string, any[]][])
    .filter(([groupName, items]) =>
      items.some(item => matchesCategory(groupName, item, aliases))
    )
    .flatMap(([, items]) => items)
    .filter(item => !BAD_RANDOM.test(itemText(item)));
}

function selectOne(
  state: State,
  indexes: any,
  aliases: readonly string[],
): void {
  const candidates = getAllCategoryItems(indexes, aliases);
  const item = pickRandom(candidates);
  if (!item) return;

  const variant = getVariant(item);
  if (variant !== null) selectItem(state, item.itemId, variant);
}

function selectHumanHead(state: State, indexes: any, gender: "male" | "female"): void {
  const all = (Object.values(indexes.byTypeName).flat() as any[]);
  const candidates = all.filter(item => {
    const t = itemText(item);
    return t.includes("human") &&
      t.includes(gender) &&
      !BAD_RANDOM.test(t);
  });

  const item = pickRandom(candidates);
  if (!item) return;

  // Human heads normally use light/medium/dark variants.
  const variants = item.variants?.length
    ? item.variants
    : (item.recolors?.flatMap((r: any) => r.variants ?? []) ?? []);
  const skin = variants.filter((v: string) =>
    /light|medium|dark|tan|brown/i.test(v)
  );
  selectItem(state, item.itemId, pickRandom(skin.length ? skin : variants) ?? "light");
}

/** Random Human using the exact ItemLite property: type_name. */
export function randomizeHuman(state: State, mode: RandomHumanMode = "human"): void {
  if (!configuredCatalog || !configuredCatalog.isIndexReady()) return;

  const indexes = configuredCatalog.getMetadataIndexes().unwrapOr(null);
  if (!indexes) return;

  const gender: "male" | "female" =
    mode === "male" ? "male" :
    mode === "female" ? "female" :
    Math.random() < 0.5 ? "male" : "female";

  state.bodyType = gender;
  state.selections = {};

  // Body Type is state.bodyType.
  // Select all categories requested by the user.
  selectOne(state, indexes, HUMAN_CATEGORIES[0]); // Body / Body color + shadow
  selectHumanHead(state, indexes, gender);        // Head / Heads

  for (let i = 2; i < HUMAN_CATEGORIES.length; i++) {
    // Keep core appearance/clothes always present.
    const required = [2, 7, 9, 10, 11].includes(i); // Faces, Arms, Torso, Legs, Feet
    if (!required && Math.random() < 0.25) continue;
    selectOne(state, indexes, HUMAN_CATEGORIES[i]);
  }

  getStateDeps().redraw();
}

export function randomizeVillager(state: State): void {
  randomizeHuman(state, "villager");
}
