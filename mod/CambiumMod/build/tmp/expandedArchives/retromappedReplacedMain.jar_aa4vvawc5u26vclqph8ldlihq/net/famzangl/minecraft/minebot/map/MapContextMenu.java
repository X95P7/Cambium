package net.famzangl.minecraft.minebot.map;

import java.util.Hashtable;
import java.util.Map.Entry;

import javax.swing.JLabel;
import javax.swing.JMenuItem;
import javax.swing.JPopupMenu;
import javax.swing.JSeparator;

import net.minecraft.util.BlockPos;

public class MapContextMenu extends JPopupMenu {
	private final BlockPos pos;

	public static final class CommandMenuItem extends JMenuItem {
		private final String command;

		public CommandMenuItem(String label, String command, BlockPos position) {
			Hashtable<String, String> replace = new Hashtable<String, String>();

			replace.put("x", position.func_177958_n() + "");
			replace.put("y", position.func_177956_o() + "");
			replace.put("z", position.func_177952_p() + "");
			replace.put("cx", (position.func_177958_n() + .5) + "");
			replace.put("cy", (position.func_177956_o() + .5) + "");
			replace.put("cz", (position.func_177952_p() + .5) + "");

			for (Entry<String, String> r : replace .entrySet()) {
				while (command.contains("{" + r.getKey() + "}")) {
					command = command.replace("{" + r.getKey() + "}", r.getValue());
				}
			}
			this.command = command;
			setText(label);
			setToolTipText(command);
			setEnabled(false);
		}
	}

	public MapContextMenu(BlockPos pos) {
		this.pos = pos;
		JLabel headline = new JLabel("<html><p><b>" + pos.func_177958_n() + ", " + pos.func_177956_o() + ", "
				+ pos.func_177952_p() + "</b></p></html>");
		headline.setAlignmentX(.5f);
		add(headline);
		add(new JSeparator());

		add(new CommandMenuItem("Walk to this position", "/minebot walk {cx} {cz}", pos));
		add(new JSeparator());
		add(new CommandMenuItem("Set position 1", "/minebuild pos1 {x} ~0 {z}", pos));
		add(new CommandMenuItem("Set position 2", "/minebuild pos2 {x} ~0 {z}", pos));
	}

}
