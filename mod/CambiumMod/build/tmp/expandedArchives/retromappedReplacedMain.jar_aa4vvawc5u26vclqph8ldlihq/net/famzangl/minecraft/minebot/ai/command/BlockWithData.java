package net.famzangl.minecraft.minebot.ai.command;

import java.util.ArrayList;
import java.util.Arrays;

import net.famzangl.minecraft.minebot.ai.ColoredBlockItemFilter;
import net.famzangl.minecraft.minebot.ai.path.world.BlockMetaSet;
import net.famzangl.minecraft.minebot.ai.path.world.BlockSet;
import net.famzangl.minecraft.minebot.ai.task.inventory.ItemWithSubtype;
import net.famzangl.minecraft.minebot.build.block.WoodType;
import net.famzangl.minecraft.minebot.build.block.WoodType.LogDirection;
import net.minecraft.block.Block;
import net.minecraft.block.state.IBlockState;
import net.minecraft.init.Blocks;
import net.minecraft.item.EnumDyeColor;

import org.apache.commons.lang3.ArrayUtils;

/**
 * This is the object wrapper for a block (id) and meta value pair. You can use
 * it to make the code cleaner.
 * 
 * It also provides methods to convert from blockid+meta to simple block id or
 * meta.
 * 
 * @see BlockWithDataOrDontcare
 * @author Michael Zangl
 *
 */
public class BlockWithData extends BlockWithDataOrDontcare {

	private static class NicerMetaValue {
		private final BlockSet forBlocks;
		private final String[] values;

		public NicerMetaValue(BlockSet forBlocks, String[] values) {
			super();
			if (values.length != 16) {
				throw new IllegalArgumentException();
			}
			this.forBlocks = forBlocks;
			this.values = values;
		}

		@Override
		public String toString() {
			return "NicerMetaValue [forBlocks=" + forBlocks + ", values="
					+ Arrays.toString(values) + "]";
		}
	}

	private static final String[] LOG_AXIS_NAMES = new String[] { "y", "x",
			"z", "none" };

	private static ArrayList<NicerMetaValue> nicerMeta = new ArrayList<BlockWithData.NicerMetaValue>();

	static {
		String[] colors = new String[16];
		for (EnumDyeColor color : EnumDyeColor.values()) {
			colors[color.func_176765_a()] = color.func_176610_l();
		}
		nicerMeta.add(new NicerMetaValue(
				ColoredBlockItemFilter.COLORABLE_BLOCKS, colors));

		String[] plankTypes = new String[16];
		String[] log = new String[16];
		String[] log2 = new String[16];
		for (WoodType woodType : WoodType.values()) {
			plankTypes[woodType.plankType.func_176839_a()] = woodType.plankType
					.toString();
			String[] logArray = woodType.block == Blocks.field_150364_r ? log : log2;
			for (LogDirection d : LogDirection.values()) {
				logArray[d.higherBits + woodType.lowerBits] = woodType.plankType
						.toString() + ":" + d.axis.toString();
			}
		}
		nicerMeta.add(new NicerMetaValue(new BlockSet(Blocks.field_150344_f),
				plankTypes));
		nicerMeta.add(new NicerMetaValue(new BlockSet(Blocks.field_150364_r), log));
		nicerMeta.add(new NicerMetaValue(new BlockSet(Blocks.field_150363_s), log2));
	}

	static BlockWithDataOrDontcare fromNiceMeta(Block block, String meta) {
		for (NicerMetaValue n : nicerMeta) {
			if (n.forBlocks.containsAny(block.func_149682_b(block))) {
				int index = ArrayUtils.indexOf(n.values, meta);
				if (index >= 0) {
					return new BlockWithData(block, index);
				}
			}
		}
		throw new IllegalArgumentException("Could not understand meta value: "
				+ meta + " for " + block);
	}

	public BlockWithData(int blockWithMeta) {
		super(blockWithMeta);
	}

	public BlockWithData(Block block, int meta) {
		this(Block.func_149682_b(block), meta);
	}

	public BlockWithData(int blockId, int meta) {
		this(toBlockWithMeta(blockId, meta));
	}

	public static int toBlockWithMeta(int blockId, int meta) {
		return (blockId << 4) | (meta & 0xf);
	}

	@Override
	public String toBlockString() {
		return getBlockString() + ":" + getMetaString();
	}

	protected String getMetaString() {
		int value = getMetaValue();
		int blockId = getBlockId();
		for (NicerMetaValue n : nicerMeta) {
			if (n.forBlocks.containsAny(blockId)) {
				String str = n.values[value];
				if (str != null) {
					return str;
				}
			}
		}
		return value + "";
	}

	public int getMetaValue() {
		return blockIdWithMeta & 0xf;
	}

	@Override
	public BlockSet toBlockSet() {
		return new BlockMetaSet(blockIdWithMeta);
	}

	@Override
	public boolean containedIn(BlockSet blockSet) {
		return blockSet.containsWithMeta(blockIdWithMeta);
	}

	public int getBlockWithMeta() {
		return blockIdWithMeta;
	}

	public ItemWithSubtype getItemType() {
		return new ItemWithSubtype(getBlockId(), getMetaValue());
	}

	public IBlockState getBlockState() {
		return (IBlockState) Block.field_176229_d.func_148745_a(blockIdWithMeta);
	}
}
