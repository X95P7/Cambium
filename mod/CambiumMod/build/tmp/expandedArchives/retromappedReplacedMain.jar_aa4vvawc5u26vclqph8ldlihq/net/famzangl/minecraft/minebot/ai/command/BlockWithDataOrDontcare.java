package net.famzangl.minecraft.minebot.ai.command;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.task.inventory.ItemWithSubtype;
import net.minecraft.block.Block;
import net.minecraft.block.state.IBlockState;
import net.minecraft.init.Blocks;
import net.minecraft.util.ResourceLocation;

public abstract class BlockWithDataOrDontcare {

	public static class IllegalBlockNameException extends
			IllegalArgumentException {

		public IllegalBlockNameException() {
			super();
		}

		public IllegalBlockNameException(String message, Throwable cause) {
			super(message, cause);
		}

		public IllegalBlockNameException(String s) {
			super(s);
		}

		public IllegalBlockNameException(Throwable cause) {
			super(cause);
		}

		@Override
		public String toString() {
			return "IllegalBlockNameException []";
		}

	}

	private static final BlockWithDataOrDontcare AIR = new BlockWithDontcare(0);
	protected final int blockIdWithMeta;

	public BlockWithDataOrDontcare(int blockWithMeta) {
		blockIdWithMeta = blockWithMeta;
	}

	/**
	 * Convers a string to a block with data. Also accepts the blocktype:meta
	 * for specifying subtypes and prefixes.
	 * 
	 * @param blockWithMeta
	 *            The string to look up
	 * @return The BlockWithData object
	 * @throws IllegalBlockNameException
	 *             For illegal input.
	 */
	public static BlockWithDataOrDontcare getFromString(String blockWithMeta) {
		// Works on minecraft:dirt:1
		Matcher matcher = Pattern.compile("^([\\w\\:]+?)(?:\\:(\\w+))?$").matcher(
				blockWithMeta);
		if (!matcher.matches()) {
			throw new IllegalBlockNameException("Illegal block name: "
					+ blockWithMeta);
		}
		// Air handled specially. Minecraft returns it on invalid names.
		if (Pattern.compile("^(minecraft\\:)air$").matcher(blockWithMeta)
				.matches()) {
			return AIR;
		}

		Block block = (Block) Block.field_149771_c.func_82594_a(new ResourceLocation(matcher.group(1)));
		if (block == null || block == Blocks.field_150350_a) {
			// minecraft:dirt case
			block = (Block) Block.field_149771_c.func_82594_a(new ResourceLocation(blockWithMeta));
			matcher = null;
		}
		if (block == null || block == Blocks.field_150350_a) {
			throw new IllegalBlockNameException(
					"Could not understand block name: " + blockWithMeta);
		} else if (matcher == null || matcher.group(2) == null
				|| matcher.group(2).matches("\\*?")) {
			return new BlockWithDontcare(block);
		} else if (matcher.group(2).matches("^(1[0-5]|\\d)$")) {
			int meta = Integer.parseInt(matcher.group(2));
			return new BlockWithData(block, meta);
		} else {
			return BlockWithData.fromNiceMeta(block, matcher.group(2));
		}
	}

	public static ArrayList<String> getAllStrings() {
		Set<ResourceLocation> keys = Block.field_149771_c.func_148742_b();
		ArrayList<String> strings = new ArrayList<String>();
		for (ResourceLocation k : keys) {
			// candidate found
			strings.add(k.toString());

			Block b = (Block) Block.field_149771_c.func_82594_a(k);
			HashSet<IBlockState> states = new HashSet<IBlockState>();
			for (int i = 0; i < 16; i++) {
				try {
				IBlockState state = b.func_176203_a(i);
				if (!states.contains(state)) {
					states.add(state);
				}
				} catch (IllegalArgumentException e) {
					// ignored
				}
			}
			if (states.size() > 1) {
				for (IBlockState state : states) {
					BlockWithData withData = new BlockWithData(b,
							b.func_176201_c(state));
					strings.add(k + ":" + withData.getMetaString());
				}
			}
		}
		return strings;
	}

	public Block getBlock() {
		return Block.func_149729_e(getBlockId());
	}

	public int getBlockId() {
		return blockIdWithMeta >> 4;
	}

	public abstract String toBlockString();

	@Override
	public String toString() {
		return toBlockString();
	}

	protected String getBlockString() {
		Block block = getBlock();
		final ResourceLocation name = ((ResourceLocation) Block.field_149771_c
				.func_177774_c(block));
		String domain = name.func_110624_b().equals("minecraft") ? ""
				: name.func_110624_b() + ":";
		String blockName = domain + name.func_110623_a();
		return blockName;
	}

	public abstract BlockSet toBlockSet();

	public abstract boolean containedIn(BlockSet blockSet);

	public abstract ItemWithSubtype getItemType();

}
