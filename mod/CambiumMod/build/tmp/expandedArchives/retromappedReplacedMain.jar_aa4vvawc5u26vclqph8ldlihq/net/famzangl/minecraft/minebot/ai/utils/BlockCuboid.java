package net.famzangl.minecraft.minebot.ai.utils;

import net.famzangl.minecraft.minebot.ai.path.world.Pos;
import net.famzangl.minecraft.minebot.ai.path.world.WorldData;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.Vec3i;

/**
 * This is cuboid of blocks.
 * <p>
 * It may not be empty.
 * 
 * @author Michael Zangl
 */
public class BlockCuboid extends BlockArea {
	/**
	 * The minimum x, y, z coordinate
	 */
	private BlockPos min;
	/**
	 * The maximum x, y, z coordinate that is in the cuboid.
	 */
	private BlockPos max;

	public BlockCuboid(BlockPos p1, BlockPos p2) {
		min = Pos.minPos(p1, p2);
		max = Pos.maxPos(p1, p2);
	}

	@Override
	public boolean contains(WorldData world, int x, int y, int z) {
		return min.func_177958_n() <= x && x <= max.func_177958_n() && min.func_177956_o() <= y
				&& y <= max.func_177956_o() && min.func_177952_p() <= z && z <= max.func_177952_p();
	}

	public BlockPos getMax() {
		return max;
	}

	public BlockPos getMin() {
		return min;
	}

	public int getVolume() {
		return (max.func_177958_n() - min.func_177958_n() + 1) * (max.func_177956_o() - min.func_177956_o() + 1)
				* (max.func_177952_p() - min.func_177952_p() + 1);
	}

	@Override
	public void accept(AreaVisitor v, WorldData world) {
		int minY = min.func_177956_o();
		int maxY = max.func_177956_o();
		for (int y = minY; y <= maxY; y++) {
			acceptY(v, y, world);
		}
	}

	private void acceptY(AreaVisitor v, int y, WorldData world) {
		int minZ = min.func_177952_p();
		int maxZ = max.func_177952_p();
		int minX = min.func_177958_n();
		int maxX = max.func_177958_n();
		for (int z = minZ; z <= maxZ; z++) {
			for (int x = minX; x <= maxX; x++) {
				v.visit(world, x, y, z);
			}
		}
	}

	/**
	 * Extend in x and z directions.
	 * 
	 * @param extend
	 *            how much
	 * @return The extended cuboid.
	 */
	public BlockCuboid extendXZ(int extend) {
		return new BlockCuboid(min.func_177982_a(-extend, 0, -extend), max.func_177982_a(extend, 0,
				extend));
	}

	public BlockCuboid extend(int amount, EnumFacing direction) {
		return boundsWith(move(amount, direction));
	}

	private BlockCuboid boundsWith(BlockCuboid other) {
		return new BlockCuboid(Pos.minPos(min, other.min), Pos.maxPos(max, other.max));
	}

	public BlockCuboid move(int amount, EnumFacing direction) {
		return move(Pos.ZERO.func_177967_a(direction, amount));
	}

	public BlockCuboid move(Vec3i vec) {
		return new BlockCuboid(min.func_177971_a(vec), max.func_177971_a(vec));
	}

	@Override
	public String toString() {
		return "BlockCuboid [min=" + min + ", max=" + max + "]";
	}
}
