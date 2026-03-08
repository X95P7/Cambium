package net.famzangl.minecraft.minebot.ai.path.world;

import net.famzangl.minecraft.minebot.ai.command.BlockWithData;
import net.minecraft.block.Block;
import net.minecraft.block.BlockTorch;
import net.minecraft.block.BlockWallSign;
import net.minecraft.block.state.IBlockState;
import net.minecraft.client.entity.EntityPlayerSP;
import net.minecraft.client.multiplayer.WorldClient;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;
import net.minecraft.util.EnumFacing;
import net.minecraft.util.Vec3;
import net.minecraft.world.chunk.Chunk;
import net.minecraft.world.chunk.storage.ExtendedBlockStorage;

/**
 * This is a world that has some deltas attached to it. This may represent a
 * world state in the future.
 * 
 * @author Michael Zangl
 */
public class WorldData {
	private static final int BARRIER_ID = Block.func_149682_b(Blocks.field_180401_cv) << 4;
	private static final int AIR_ID = 0;
	private static final int CACHE_ENTRIES = 10;
	/**
	 * A cache pos that may never occur naturally.
	 */
	private static final int CACHE_INVALID = 0x10000000;
	private static final double FLOOR_HEIGHT = .55;

	public static abstract class ChunkAccessor {
		protected ExtendedBlockStorage[] blockStorage;

		public int getBlockIdWithMeta(int x, int y, int z) {
			int blockId = 0;
			if (y >> 4 < blockStorage.length) {
				final ExtendedBlockStorage extendedblockstorage = blockStorage[y >> 4];

				if (extendedblockstorage != null) {
					final int lx = x & 15;
					final int ly = y & 15;
					final int lz = z & 15;
					blockId = extendedblockstorage.func_177487_g()[ly << 8 | lz << 4
							| lx] & 0xffff;
				}
			}

			return blockId;
		}
	}

	public static class ChunkAccessorUnmodified extends ChunkAccessor {

		public ChunkAccessorUnmodified(Chunk chunk) {
			blockStorage = chunk.func_76587_i();
		}
	}

	private long[] cachedPos = new long[CACHE_ENTRIES];
	private ChunkAccessor[] cached = new ChunkAccessor[CACHE_ENTRIES];

	private int chunkCacheReplaceCounter = 0;

	protected final WorldClient theWorld;
	private EntityPlayerSP thePlayerToGetPositionFrom;

	public WorldData(WorldClient theWorld,
			EntityPlayerSP thePlayerToGetPositionFrom) {
		this.theWorld = theWorld;
		this.thePlayerToGetPositionFrom = thePlayerToGetPositionFrom;
	}

	/**
	 * A fast method that gets a block id for a given position. Use it if you
	 * need to scan many blocks, since the default minecraft block lookup is
	 * slow. For x<0 or x>= 256 it returns bedrock, to make routing easy.
	 * 
	 * @param x
	 * @param y
	 * @param z
	 * @return
	 */
	public int getBlockIdWithMeta(int x, int y, int z) {
		if (y < 0 || y >= 258) {
			return BARRIER_ID;
		} else if (y >= 256) {
			return AIR_ID;
		}
		ChunkAccessor a = getChunkAccessor(x, z);

		// chunk.getBlock(x & 15, y, z & 15);

		return a == null ? BARRIER_ID : a.getBlockIdWithMeta(x, y, z);
	}

	private ChunkAccessor getChunkAccessor(int x, int z) {
		int chunkX = x >> 4;
		int chunkZ = z >> 4;
		ChunkAccessor chunk = null;
		long posForCache = cachePosition(chunkX, chunkZ);

		for (int i = 0; i < CACHE_ENTRIES; i++) {
			if (cachedPos[i] == posForCache) {
				return cached[i];
			}
		}

		chunk = generateChunkAccessor(chunkX, chunkZ);

		cachedPos[chunkCacheReplaceCounter] = posForCache;
		cached[chunkCacheReplaceCounter] = chunk;

		chunkCacheReplaceCounter++;
		if (chunkCacheReplaceCounter >= CACHE_ENTRIES) {
			chunkCacheReplaceCounter = 0;
		}
		return chunk;
	}

	protected ChunkAccessor generateChunkAccessor(int chunkX, int chunkZ) {
		return new ChunkAccessorUnmodified(theWorld.func_72964_e(
				chunkX, chunkZ));
	}

	/**
	 * A unique long for each chunk.
	 * 
	 * @param chunkX
	 * @param chunkZ
	 * @return
	 */
	protected long cachePosition(int chunkX, int chunkZ) {
		return (long) chunkX << 32 | (chunkZ & 0xffffffffl);
	}

	public void invalidateChunkCache() {
		for (int i = 0; i < CACHE_ENTRIES; i++) {
			// chunk coord would be invalid.
			cachedPos[i] = CACHE_INVALID;
		}
	}

	public WorldClient getBackingWorld() {
		return theWorld;
	}

	public int getBlockId(BlockPos pos) {
		return getBlockId(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	public int getBlockId(int x, int y, int z) {
		return getBlockIdWithMeta(x, y, z) >> 4;
	}

	public int getBlockIdWithMeta(BlockPos pos) {
		return getBlockIdWithMeta(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	public IBlockState getBlockState(BlockPos pos) {
		IBlockState iblockstate = (IBlockState) Block.field_176229_d
				.func_148745_a(getBlockIdWithMeta(pos));
		return iblockstate != null ? iblockstate : Blocks.field_150350_a.func_176223_P();
	}

	public boolean isSideTorch(BlockPos pos) {
		int id = getBlockIdWithMeta(pos);
		// TODO: Convert this to a block set.
		return BlockSets.TORCH.containsWithMeta(id)
				&& getBlockState(pos).func_177229_b(BlockTorch.field_176596_a) != EnumFacing.UP;
	}

	public BlockPos getHangingOnBlock(BlockPos pos) {
		IBlockState meta = getBlockState(pos);
		EnumFacing facing = null;
		if (BlockSets.TORCH.contains(meta.func_177230_c())) {
			facing = getTorchDirection(meta);
		} else if (meta.func_177230_c().equals(Blocks.field_150444_as)) {
			facing = getSignDirection(meta);
			// TODO Ladder and other hanging blocks.
		} else if (BlockSets.FEET_CAN_WALK_THROUGH.contains(meta)) {
			facing = EnumFacing.UP;
		}
		return facing == null ? null : pos.func_177967_a(facing, -1);
	}

	/**
	 * Get the sign/ladder/dispenser/dropper direction
	 * 
	 * @param meta
	 * @return
	 */
	private EnumFacing getSignDirection(IBlockState metaValue) {
		return (EnumFacing) metaValue.func_177229_b(BlockWallSign.field_176412_a);
	}

	// TODO: Move somewhere else.
	/**
	 * The direction the torch is facing. Default would be up.
	 * 
	 * @param metaValue
	 * @return
	 */
	public EnumFacing getTorchDirection(IBlockState metaValue) {
		return (EnumFacing) metaValue.func_177229_b(BlockTorch.field_176596_a);
	}

	/**
	 * Gets the grid player position. A player is always referenced by the foot
	 * block for this bot. The block below the player is the floor block (or
	 * ground block). A slab below the player is still considered ground, so the
	 * floor block is the block the player above that slab. Flat blocks or
	 * blocks the player can walk through are not considered ground, so they are
	 * the floor block instead.
	 * 
	 * @return
	 */
	public BlockPos getPlayerPosition() {
		final int x = (int) Math.floor(thePlayerToGetPositionFrom.field_70165_t);
		final int y = (int) Math.floor(thePlayerToGetPositionFrom
				.func_174813_aQ().field_72338_b + FLOOR_HEIGHT);
		final int z = (int) Math.floor(thePlayerToGetPositionFrom.field_70161_v);
		return new BlockPos(x, y, z);
	}

	public Vec3 getExactPlayerPosition() {
		return new Vec3(thePlayerToGetPositionFrom.field_70165_t,
				thePlayerToGetPositionFrom.func_174813_aQ().field_72338_b,
				thePlayerToGetPositionFrom.field_70161_v);
	}

	public BlockBounds getBlockBounds(BlockPos pos) {
		return getBlockBounds(pos.func_177958_n(), pos.func_177956_o(), pos.func_177952_p());
	}

	public BlockBounds getBlockBounds(int x, int y, int z) {
		BlockBounds res = BlockBounds.forBlockWithMeta(getBlockIdWithMeta(x, y,
				z));
		if (res == BlockBounds.UNKNOWN_BLOCK) {
			// TODO: Replace this.
			WorldClient world = getBackingWorld();
			BlockPos pos = new BlockPos(x, y, z);
			Block block = world.func_180495_p(pos).func_177230_c();
			block.func_180654_a(world, pos);

			return new BlockBounds(block.func_149704_x(),
					block.func_149753_y(), block.func_149665_z(),
					block.func_149669_A(), block.func_149706_B(),
					block.func_149693_C());
		}
		return res;
	}

	/**
	 * Returns the current state of the world if this world is a state in the
	 * future.
	 * 
	 * @return A world.
	 */
	public WorldData getCurrentState() {
		return this;
	}

	public BlockWithData getBlock(BlockPos position) {
		return new BlockWithData(getBlockIdWithMeta(position));
	}

	public long getWorldTime() {
		return theWorld.func_82737_E();
	}

}