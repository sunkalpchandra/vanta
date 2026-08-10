import { describe, expect, it } from "vitest";
import { getStarred, toggleStar } from "./starred";

function memoryStorage(initial: string | null = null) {
  let value = initial;
  return {
    getItem: () => value,
    setItem: (_: string, v: string) => {
      value = v;
    },
  };
}

describe("starred store", () => {
  it("starts empty and survives garbage", () => {
    expect(getStarred(memoryStorage(null))).toEqual([]);
    expect(getStarred(memoryStorage("not json{{"))).toEqual([]);
    expect(getStarred(memoryStorage('{"a":1}'))).toEqual([]);
    expect(getStarred(memoryStorage('[1,"x",2.5,3]'))).toEqual([1, 3]);
  });

  it("toggles on and off", () => {
    const storage = memoryStorage();
    expect(toggleStar(5, storage)).toEqual([5]);
    expect(toggleStar(9, storage)).toEqual([5, 9]);
    expect(toggleStar(5, storage)).toEqual([9]);
    expect(getStarred(storage)).toEqual([9]);
  });
});
