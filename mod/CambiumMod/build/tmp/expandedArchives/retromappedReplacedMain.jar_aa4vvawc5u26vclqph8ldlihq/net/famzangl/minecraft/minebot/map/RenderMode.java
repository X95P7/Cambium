package net.famzangl.minecraft.minebot.map;

import java.util.Hashtable;

import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.path.world.WorldData;
import net.famzangl.minecraft.minebot.ai.utils.BlockCounter;
import net.famzangl.minecraft.minebot.ai.utils.BlockCuboid;
import net.minecraft.block.material.MapColor;
import net.minecraft.block.state.IBlockState;
import net.minecraft.init.Blocks;
import net.minecraft.util.BlockPos;
import net.minecraft.world.chunk.Chunk;

public enum RenderMode {
	UNDERGROUND(new UndergroundRenderer(), "-underground"), MAP(
			new MapRenderer(), ""), BIOME(new BiomeRenderer(), "-biome");
	private static final BlockSet GLOBAL_COVER_BLACKLIST = new BlockSet(
			Blocks.field_150376_bx, Blocks.field_150333_U, Blocks.field_180389_cP,
			Blocks.field_150350_a);
	private static final BlockSet IGNORED_COVER_BLOCKS = new BlockSet(
			Blocks.field_150350_a, Blocks.field_150362_t, Blocks.field_150361_u, Blocks.field_150364_r,
			Blocks.field_150363_s, Blocks.field_150478_aa, Blocks.field_150355_j, Blocks.field_150358_i,
			Blocks.field_150392_bi, Blocks.field_150353_l, Blocks.field_150356_k,
			Blocks.field_150433_aE, Blocks.field_150431_aC, Blocks.field_150432_aD)
			.unionWith(GLOBAL_COVER_BLACKLIST);
	private static final BlockSet UNDERGROUND_BLOCKS = new BlockSet(
			Blocks.field_150350_a, Blocks.field_150478_aa);
	private static final BlockSet STRUCTURE_BLOCKS = new BlockSet(
			Blocks.field_180407_aO, Blocks.field_150378_br, Blocks.field_150377_bs,
			Blocks.field_150342_X, Blocks.field_180397_cI, Blocks.field_150344_f,
			Blocks.field_150385_bj, Blocks.field_150388_bm, Blocks.field_150478_aa);
	private static final BlockSet INTERESTING_BLOCKS = new BlockSet(
			Blocks.field_150486_ae, Blocks.field_150474_ac, Blocks.field_150340_R);

	private interface IRenderer {
		/**
		 * Gets the color for one pixel of the map.
		 * 
		 * @param world
		 *            The world to use.
		 * @param chunk
		 *            The chunk we are rendering
		 * @param dx
		 *            World x coordinate
		 * @param dz
		 *            World y coordinate
		 * @return The rgba color.
		 */
		int getColor(WorldData world, Chunk chunk, int dx, int dz);
	}

	private static class UndergroundRenderer implements RenderMode.IRenderer {

		@Override
		public int getColor(WorldData world, Chunk chunk, int dx, int dz) {
			int h = chunk.func_76611_b(dx & 0xf, dz & 0xf) + 1;
			while (h > 3
					&& IGNORED_COVER_BLOCKS.contains(chunk.func_177438_a(dx, h, dz))) {
				h--;
			}
			BlockCuboid area = new BlockCuboid(new BlockPos(dx, 0, dz),
					new BlockPos(dx, h, dz));

			int[] count = BlockCounter.countBlocks(world, area,
					STRUCTURE_BLOCKS, INTERESTING_BLOCKS, UNDERGROUND_BLOCKS);
			// structure
			int r = Math.min((int) (count[0] / 6.0 * 0xff), 0xff);
			// interesting
			int g = Math.min((int) (count[1] / 2.0 * 0xff), 0xff);
			// underground
			int b = Math.min((int) (Math.sqrt(count[2]) / 6.0 * 0xff), 0xff);
			return 0xff000000 | (r << 16) | (g << 8) | b;
		}
	}

	private static class MapRenderer implements RenderMode.IRenderer {
		@Override
		public int getColor(WorldData world, Chunk chunk, int dx, int dz) {
			int h = chunk.func_76611_b(dx & 0xf, dz & 0xf) + 1;
			IBlockState state;
			do {
				--h;
				state = chunk.func_177435_g(new BlockPos(dx, h, dz));
			} while ((GLOBAL_COVER_BLACKLIST.contains(state.func_177230_c()) || state
					.func_177230_c().func_180659_g(state) == MapColor.field_151660_b)
					&& h > 0);

			if (state.func_177230_c() == Blocks.field_150322_A || state.func_177230_c() == Blocks.field_150372_bz) {
				return 0xffb4ad8a;
			}
			
			MapColor color = (state.func_177230_c().func_180659_g(state));
			return getColor(color);
		}

		private int getColor(MapColor color) {
			return 0xff000000 | color.field_76291_p;
		}
	}

	private static class BiomeRenderer implements RenderMode.IRenderer {
		private static final Hashtable<Integer, Integer> COLORS = new Hashtable<Integer, Integer>();
		private static final Integer DEFAULT_COLOR = 0xff000000;

		static {
			COLORS.put(0, 0xff0036ff); // Ocean
			COLORS.put(1, 0xff5fd15c); // Plains
			COLORS.put(2, 0xffe8e874); // Desert
			COLORS.put(3, 0xff8b6d50); // Extreme Hills
			COLORS.put(4, 0xff1ea31a); // Forest
			COLORS.put(5, 0xff004d24); // Taiga
			COLORS.put(6, 0xff008340); // Swampland
			COLORS.put(7, 0xff315dff); // River
			COLORS.put(8, 0xffba4627); // Hell (Nether)
			COLORS.put(9, 0xff31ffa3); // Sky (End)
			COLORS.put(10, 0xff6686ff); // Frozen Ocean
			COLORS.put(11, 0xff86a0ff); // Frozen River
			COLORS.put(12, 0xffe9eeff); // Ice Plains
			COLORS.put(13, 0xffe9eeff); // Ice Mountains
			COLORS.put(14, 0xffff0000);// 0xffcdbaba); // Mushroom Island
			COLORS.put(15, 0xffff0000);// 0xffcdbaba); // Mushroom Island
										// Shore
			COLORS.put(16, 0xffe0e02d); // Beach
			COLORS.put(17, 0xffe8e874); // Desert Hills
			COLORS.put(18, 0xff1ea31a); // Forest Hills
			COLORS.put(19, 0xff004d24); // Taiga Hills
			COLORS.put(20, 0xff8b6d50); // Extreme Hills Edge
			COLORS.put(21, 0xff47bd21); // Jungle
			COLORS.put(22, 0xff47bd21); // Jungle Hills
			COLORS.put(23, 0xff47bd21); // Jungle Edge
			COLORS.put(24, 0xff002098); // Deep Ocean
			COLORS.put(25, 0xff989898); // Stone Beach
			COLORS.put(26, 0xffe0e069); // Cold Beach
			COLORS.put(27, 0xff31a32d); // Birch Forest
			COLORS.put(28, 0xff31a32d); // Birch Forest Hills
			COLORS.put(29, 0xff125d16); // Roofed Forest
			COLORS.put(30, 0xff69c594); // Cold Taiga
			COLORS.put(31, 0xff69c594); // Cold Taiga Hills
			COLORS.put(32, 0xff00391a); // Mega Taiga
			COLORS.put(33, 0xff00391a); // Mega Taiga Hills
			COLORS.put(34, 0xff8b6d50); // Extreme Hills+
			COLORS.put(35, 0xffa0ba00); // Savanna
			COLORS.put(36, 0xffa0ba00); // Savanna Plateau
			COLORS.put(37, 0xffe8822e); // Mesa
			COLORS.put(38, 0xffe8822e); // Mesa Plateau F
			COLORS.put(39, 0xffe8822e); // Mesa Plateau
			COLORS.put(129, 0xff5fd15c); // Sunflower Plains
			COLORS.put(130, 0xffe8e874); // Desert M
			COLORS.put(131, 0xff8b6d50); // Extreme Hills M
			COLORS.put(132, 0xff1ea31a); // Flower Forest
			COLORS.put(133, 0xff004d24); // Taiga M
			COLORS.put(134, 0xff008340); // Swampland M
			COLORS.put(140, 0xff89d9e8); // Ice Plains Spikes
			COLORS.put(149, 0xff47bd21); // Jungle M
			COLORS.put(151, 0xff47bd21); // JungleEdge M
			COLORS.put(155, 0xff31a32d); // Birch Forest M
			COLORS.put(156, 0xff31a32d); // Birch Forest Hills M
			COLORS.put(157, 0xff125d16); // Roofed Forest M
			COLORS.put(158, 0xff69c594); // Cold Taiga M
			COLORS.put(160, 0xff00391a); // Mega Spruce Taiga
			COLORS.put(161, 0xff00391a); // Mega Spruce Taiga Hills
			COLORS.put(162, 0xff8b6d50); // Extreme Hills+ M
			COLORS.put(163, 0xffa0ba00); // Savanna M
			COLORS.put(164, 0xffa0ba00); // Savanna Plateau M
			COLORS.put(165, 0xffe8822e); // Mesa (Bryce)
			COLORS.put(166, 0xffe8822e); // Mesa Plateau F M
			COLORS.put(167, 0xffe8822e); // Mesa Plateau M
		}

		@Override
		public int getColor(WorldData world, Chunk chunk, int dx, int dz) {
			int i = dx & 15;
			int j = dz & 15;
			int k = chunk.func_76605_m()[j << 4 | i] & 255;
			// assume it is already loaded. If not, we ignore it.
			Integer color = COLORS.get(k);
			return color != null ? color : DEFAULT_COLOR;
		}

	}

	private RenderMode.IRenderer renderer;
	private String ext;

	private RenderMode(RenderMode.IRenderer renderer, String ext) {
		this.renderer = renderer;
		this.ext = ext;
	}

	public String getExt() {
		return ext;
	}

	public int getColor(WorldData world, Chunk chunk, int dx, int dz) {
		return renderer.getColor(world, chunk, dx, dz);
	}

	public String getName() {
		return toString();
	}
}