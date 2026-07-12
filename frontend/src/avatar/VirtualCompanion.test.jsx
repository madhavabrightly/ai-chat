import { describe, expect, it } from 'vitest'
import { Box3, BoxGeometry, Group, Mesh, MeshBasicMaterial, Vector3 } from 'three'
import { normalizeAvatarRoot } from './VirtualCompanion.jsx'

describe('normalizeAvatarRoot', () => {
  it('fits a model once and places it on the stable call-stage floor', () => {
    const root = new Group()
    root.add(new Mesh(new BoxGeometry(2, 4, 1), new MeshBasicMaterial()))

    normalizeAvatarRoot(root)
    const box = new Box3().setFromObject(root)
    const size = box.getSize(new Vector3())
    const center = box.getCenter(new Vector3())

    expect(size.y).toBeCloseTo(2.82, 4)
    expect(box.min.y).toBeCloseTo(-1.46, 4)
    expect(center.x).toBeCloseTo(0, 4)
    expect(center.z).toBeCloseTo(0, 4)

    const firstPosition = root.position.clone()
    normalizeAvatarRoot(root)
    expect(root.position.equals(firstPosition)).toBe(true)
  })
})
