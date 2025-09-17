// character.js: Enhancements for character creation UI
// - Random name generator that adapts to selected class
// - Wires up the input-group button to populate the name field

(function(){
  document.addEventListener('DOMContentLoaded', function(){
    const nameInput = document.getElementById('name');
    const randomBtn = document.getElementById('randomize-name');
    const classSelect = document.getElementById('char_class');
    if (!nameInput || !randomBtn || !classSelect) return;

    // Curated fantasy-style name pools
    const pools = {
      generic: [
        'Aldric','Bryn','Caelan','Dorian','Elara','Fenn','Garrick','Helena','Isolde','Jorah','Kael','Lyra','Merric','Nerys','Orin','Perrin','Quinn','Rowan','Sylas','Tamsin','Ulric','Vera','Wren','Xan','Yara','Zephyr'
      ],
      fighter: ['Brakus','Durgan','Freya','Gunnar','Hilda','Korrin','Magda','Roderic','Sable','Thrain','Viggo','Wulfric'],
      rogue:   ['Ash','Briar','Cipher','Dax','Eve','Fable','Gale','Hex','Iris','Jinx','Kestrel','Lark'],
      mage:    ['Aelwyn','Belisar','Cyrene','Daelon','Eldrin','Faelith','Galen','Hypatia','Ilyria','Jorahm','Kaelis','Lunara'],
      cleric:  ['Ansel','Benedict','Cyril','Delphine','Elias','Fiora','Gideon','Honora','Isidore','Jorah','Lucien','Mariel'],
      ranger:  ['Arden','Briar','Cedar','Dawn','Ember','Flint','Grove','Hawk','Ivy','Jasper','Kieran','Linden'],
      druid:   ['Alder','Birch','Clover','Dew','Elder','Fern','Gale','Hazel','Iris','Juniper','Kestrel','Laurel']
    };

    function pick(arr){ return arr[Math.floor(Math.random()*arr.length)]; }

    function generateName(){
      const cls = classSelect.value;
      const list = pools[cls] || pools.generic;
      // 70% from class pool, 30% from generic, then occasionally combine two parts
      const primary = Math.random() < 0.7 ? pick(list) : pick(pools.generic);
      if (Math.random() < 0.22) {
        const second = pick(pools.generic.filter(n => n !== primary));
        return primary + ' ' + second;
      }
      return primary;
    }

    randomBtn.addEventListener('click', function(){
      nameInput.value = generateName();
      nameInput.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
})();
